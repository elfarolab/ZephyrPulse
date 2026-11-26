"""Zephyr Pulse v0.3: source-based board inventory, compact history and release intelligence."""
from __future__ import annotations
import datetime as dt
import fnmatch
import hashlib
import json
import logging
from progress import Progress, stage
import os
import re
import subprocess
from collections import defaultdict, Counter
from pathlib import PurePosixPath
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SCHEMA = '''
CREATE TABLE IF NOT EXISTS history_seen(sha TEXT PRIMARY KEY, committed TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS milestones(sha TEXT NOT NULL REFERENCES history_seen(sha) ON DELETE CASCADE,
 board TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, confidence TEXT NOT NULL, path TEXT NOT NULL,
 PRIMARY KEY(sha,board,kind,label,path));
CREATE TABLE IF NOT EXISTS vendor_activity(sha TEXT NOT NULL REFERENCES history_seen(sha) ON DELETE CASCADE,
 vendor TEXT NOT NULL, signal TEXT NOT NULL, author TEXT NOT NULL, PRIMARY KEY(sha,vendor,signal));
CREATE INDEX IF NOT EXISTS history_time ON history_seen(committed);
CREATE INDEX IF NOT EXISTS milestone_board ON milestones(board);
CREATE TABLE IF NOT EXISTS release_cache(sha TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
'''
PERIPHERALS = ['gpio','uart','i2c','spi','adc','dac','pwm','can','watchdog','counter','rtc','usb','ethernet','wifi','bluetooth','i2s','pdm','dma','flash','sdhc','display','sensor','crypto','low-power']
ALIASES = {'wdt':'watchdog','usbd':'usb','usb_device':'usb','usb_host':'usb','eth':'ethernet','netif:eth':'ethernet','netif:wifi':'wifi','bt':'bluetooth','ble':'bluetooth','netif:bt':'bluetooth','canfd':'can','can-fd':'can','pm':'low-power'}
VENDOR_ALIASES = {'stmicroelectronics':'st','stm32':'st','nordicsemi':'nordic','nordic_semiconductor':'nordic','nxp_semiconductors':'nxp','silabs':'silabs','siliconlabs':'silabs','espressif':'espressif','renesas':'renesas','ti':'ti','texas_instruments':'ti','microchip':'microchip'}


def canon_vendor(x):
    x=str(x).casefold().replace(' ','_'); return VENDOR_ALIASES.get(x,x)


def match_pattern(value, pattern):
    value, pattern = str(value).casefold(), str(pattern).strip().casefold()
    return bool(pattern) and (fnmatch.fnmatchcase(value,pattern) if any(c in pattern for c in '*?[') else pattern in value)


def matches(values, patterns):
    return any(match_pattern(v,p) for v in values for p in patterns)


def watch_match(event, boards, watch):
    text = [event.get(k,'') for k in ('subject','detail','path','commit_subject','title')]
    ids = event.get('boards', [])
    records = [boards[b] for b in ids if b in boards]
    names = text + [v for b in records for v in [b['name'],b['full_name'],b['folder'],*b['socs'],*b['targets']]]
    vendors = text + [b['vendor'] for b in records] + [b['vendor_name'] for b in records]
    return (matches(names,watch.get('boards',[])) or matches(vendors,watch.get('vendors',[])) or
            matches(text,watch.get('peripherals',[])))


def blobs(repo, sha, paths):
    """One git process for many small source files; never check out or execute upstream code."""
    if not paths: return {}
    proc=subprocess.run(['git','-C',str(repo.path),'cat-file','--batch'],input=''.join(f'{sha}:{p}\n' for p in paths).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    data=proc.stdout; pos=0; result={}
    for path in paths:
        end=data.index(b'\n',pos); header=data[pos:end].split(); pos=end+1
        if len(header)!=3 or header[1]!=b'blob': raise RuntimeError(f'Cannot read {path} at {sha}')
        size=int(header[2]); result[path]=data[pos:pos+size].decode(errors='replace'); pos+=size+1
    return result


def inventory(repo, head, db=None):
    from performance import roots, trees, load, save, digest
    relevant=['boards','dts','soc','include','drivers']
    fingerprint=digest(roots(repo,head,relevant))
    previous=load(db,'inventory') or {}
    prior_head=previous.get('head')
    # Never retain an evidence anchor from an abandoned branch after a rewrite.
    if prior_head and prior_head!=head and repo.git('merge-base',prior_head,head,allow=(0,1,128)).strip()!=prior_head:
        logging.info('Inventory cache: upstream history rewritten; refreshing evidence anchors')
        previous={}
    if previous.get('fingerprint')==fingerprint:
        boards=previous['boards']
        logging.info('Inventory cache: full hit (%d boards; hardware trees unchanged)',len(boards))
        if prior_head!=head: save(db,'inventory',{**previous,'head':head})
        return boards
    ids=trees(repo,head,relevant)
    boards, targets=_inventory(repo,head,ids,previous.get('targets',{}))
    old_boards=previous.get('boards',{})
    reused=0
    for key,b in boards.items():
        signature=digest([ids.get(b['folder']), b])
        old=old_boards.get(key,{})
        unchanged=old.get('evidence_fingerprint')==signature
        b['evidence_revision']=old['evidence_revision'] if unchanged else head
        b['evidence_fingerprint']=signature
        reused+=int(unchanged)
    logging.info('Inventory evidence anchors: %d unchanged, %d refreshed',reused,len(boards)-reused)
    save(db,'inventory',{'head':head,'fingerprint':fingerprint,'boards':boards,'targets':targets})
    return boards


def _inventory(repo, head, ids, previous_targets):
    from pulse import board_defs, yload, supported, nodes, variants
    paths=repo.git('ls-tree','-r','--name-only',head,'--','boards').splitlines()
    pathset=set(paths)
    definitions=[p for p in paths if p.endswith('/board.yml') and p.count('/')>=3]
    folders={str(PurePosixPath(p).parent) for p in definitions}
    wanted=definitions+[p for p in paths if str(PurePosixPath(p).parent) in folders and p.endswith(('.yaml','.dts','.dtsi'))]
    logging.info('Inventory: %d board definition files, %d source files to read',len(definitions),len(set(wanted)))
    with stage('Read inventory source files'):
        data=blobs(repo,head,sorted(set(wanted)))
    by_folder=defaultdict(list)
    for p in data: by_folder[str(PurePosixPath(p).parent)].append(p)
    prefixes={}
    for line in repo.git('show',f'{head}:dts/bindings/vendor-prefixes.txt',allow=(0,128)).splitlines():
        if line.strip() and not line.startswith('#') and '\t' in line:
            k,v=line.split('\t',1); prefixes[k.strip()]=v.strip()
    from hardware_evidence import EvidenceIndex
    with stage("Index revision-pinned devicetree sources"):
        evidence_index=EvidenceIndex(repo,head,previous_targets,ids)
    boards={}
    progress=Progress('Board definitions',len(definitions))
    for i,path in enumerate(definitions,1):
        progress.item(i,path)
        folder=str(PurePosixPath(path).parent)
        for name,b in board_defs(data[path]).items():
            vendor=str(b.get('vendor') or folder.split('/')[1]); key=folder+'/'+name
            meta={}; raw=[]
            for p in sorted(by_folder[folder]):
                if p.endswith('.yaml'):
                    target, features=supported(data[p]); d=yload(data[p]);
                    if target and target.split('/')[0]==name:
                        meta[target]={'features':sorted(features),'arch':str(d.get('arch','')),'ram':d.get('ram'),'flash':d.get('flash'),'path':p}
                        meta[target]['dts_evidence']=evidence_index.target(folder,target,meta[target]['arch'],p)
                elif p.endswith(('.dts','.dtsi')):
                    # Shared folder files are raw evidence, not attributed to every target.
                    for node,props in nodes(data[p]).items():
                        if props.get('status') or props.get('compatible'):
                            raw.append({'path':p,'node':node,'status':', '.join(props.get('status',())),'compatible':', '.join(props.get('compatible',()))})
            socs=[str(x['name']) for x in b.get('socs',[]) if isinstance(x,dict) and x.get('name')]
            boards[key]={'id':key,'slug':re.sub(r'[^a-z0-9-]+','-',name.lower()).strip('-')+'-'+hashlib.sha256(key.encode()).hexdigest()[:10],
                'name':name,'full_name':str(b.get('full_name',name)),'folder':folder,'vendor':canon_vendor(vendor),'vendor_name':prefixes.get(vendor,vendor),
                'doc_source': next((p for p in (folder+'/doc/'+name+'.rst',folder+'/doc/index.rst') if p in pathset and (p.endswith('/'+name+'.rst') or len(board_defs(data[path]))==1)),None),
                'socs':socs,'targets':sorted(set(meta)|{t for t in variants({name:b}) if not any(x.startswith(t+'/') for x in meta)}),'metadata':meta,'raw':raw,'source':path}
        progress.done(i)
    logging.info('Target evidence cache: %d hits, %d computed',evidence_index.hits,evidence_index.misses)
    return boards,evidence_index.results


def board_ids(event, boards, index=None):
    from pulse import board_folder
    folder=board_folder(event.get('path','')) or board_folder(event.get('subject','')+'/x')
    if not folder: return []
    options=(index.get(folder,[]) if index is not None else [k for k,b in boards.items() if b['folder']==folder])
    subject=event.get('subject','').split('/')[0]
    exact=[k for k in options if boards[k]['name']==subject]
    return exact or options


def folder_index(boards):
    index=defaultdict(list)
    for k,b in boards.items(): index[b['folder']].append(k)
    return index


def activity_vendor(path, boards_by_folder, known):
    from pulse import board_folder
    folder=board_folder(path); p=path.split('/')
    if folder:
        return sorted(set(boards_by_folder.get(folder,[]) or [canon_vendor(p[1])]))
    if p[0]=='soc' and len(p)>2 and p[1] not in ('common','arch'):
        return [canon_vendor(p[1])] if canon_vendor(p[1]) in known else []
    if p[0]=='drivers' and len(p)>2:
        return sorted({canon_vendor(x) for x in p[2:-1] if canon_vendor(x) in known})
    if path.startswith('dts/bindings/') and ',' in p[-1]:
        return [canon_vendor(p[-1].split(',')[0])]
    if p[0]=='dts' and len(p)>3 and canon_vendor(p[2]) in known:
        return [canon_vendor(p[2])]
    return []


def update_history(db,repo,head,now,boards,days=90,batch=250):
    from pulse import classify, first_parent_window
    db.executescript(SCHEMA)
    cutoff=(now-dt.timedelta(days=days)).isoformat(timespec='seconds')
    # First-parent reachability also removes records from rewritten main history.
    history = {sha: (date, hashlib.sha256(author.casefold().encode()).hexdigest())
               for sha, date, author in first_parent_window(repo, head, cutoff)}
    idx=folder_index(boards); bv={f:[boards[k]['vendor'] for k in ids] for f,ids in idx.items()}; known={b['vendor'] for b in boards.values()} | set(VENDOR_ALIASES.values())
    seen={r[0] for r in db.execute('SELECT sha FROM history_seen')}
    recent={r[0] for r in db.execute('SELECT sha FROM commits')}
    pending=[s for s in history if s not in seen]
    # Always summarize recent news; backfill older commits in bounded batches (0 = all).
    older=[s for s in pending if s not in recent]; selected=[s for s in pending if s in recent]+(older[:batch] if batch else older)
    logging.info('History: %d already processed, %d pending; %d selected this run',len(seen & history.keys()),len(pending),len(selected))
    progress=Progress('Historical commits',len(selected))
    with db:
        db.executemany('DELETE FROM history_seen WHERE sha=?',[(s,) for s in seen-history.keys()])
        for i,sha in enumerate(selected,1):
            progress.item(i,sha[:12])
            date,author=history[sha]; parent=repo.parent(sha); changes=list(repo.changes(sha,parent))
            db.execute('INSERT INTO history_seen VALUES(?,?)',(sha,date))
            events=[dict(r) for r in db.execute('SELECT * FROM events WHERE sha=?',(sha,))] if sha in recent else [dict(zip(('kind','subject','detail','confidence','path'),e)) for e in classify(repo,sha,parent,changes)]
            signals=set(); touched=set()
            for status,old,path in changes:
                path=path or old
                for vendor in activity_vendor(path,bv,known):
                    touched.add(vendor); signals.add((vendor,'hardware_changes'))
                    if path.startswith('drivers/'): signals.add((vendor,'driver_changes'))
                    if path.startswith(('tests/','samples/')) or '/tests/' in path: signals.add((vendor,'test_source_changes'))
            subject=repo.git('show','-s','--format=%s',sha).strip()
            if re.search(r'\b(fix|fixes|fixed|bugfix|regression)\b',subject,re.I):
                signals.update((v,'fix_signals') for v in touched)
            if any((p or o or '').startswith(('tests/','samples/')) for _,o,p in changes):
                signals.update((v,'test_source_changes') for v in touched)
            for e in events:
                ids=board_ids(e,boards,idx)
                if e['kind'] in ('board','board_feature','board_candidate'):
                    for key in ids:
                        # Keep only milestone labels/source references, not old commit bodies or full event records.
                        label=e['detail'].split(' Verify ')[0].split(' (source only)')[0][:240]
                        db.execute('INSERT OR IGNORE INTO milestones VALUES(?,?,?,?,?,?)',(sha,key,e['kind'],label,('candidate' if len(ids)>1 else e['confidence']),e['path']))
                        signals.add((boards[key]['vendor'],e['kind']))
                if e['kind'] in ('driver','sensor','soc'):
                    for v in activity_vendor(e['path'],bv,known): signals.add((v,e['kind']))
            db.executemany('INSERT OR IGNORE INTO vendor_activity VALUES(?,?,?,?)',[(sha,v,s,author) for v,s in signals])
            progress.done(i)
        db.execute('DELETE FROM release_cache WHERE sha NOT IN (SELECT sha FROM history_seen)')
    done=len((seen & history.keys()) | set(selected)); logging.info('History coverage: %d/%d commits',done,len(history))
    return {'days':days,'processed':done,'total':len(history),'cutoff':cutoff,'complete':done==len(history)}


def release_tags(repo, lts_lines):
    tags=[]
    for line in repo.git('for-each-ref','--format=%(refname:short)%09%(creatordate:iso-strict)%09%(objectname)','refs/tags').splitlines():
        tag,date,obj=line.split('\t'); m=re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)',tag)
        if not m: continue
        version=tuple(map(int,m.groups()))
        if version[2] == 99: continue  # Zephyr development marker, not a release.
        series=f'{version[0]}.{version[1]}'
        tags.append({'tag':tag,'date':date,'object':obj,'version':version,'series':series,'lts':series in lts_lines})
    return sorted(tags,key=lambda x:x['version'])


def tracked_releases(repo, cfg):
    """Select only the latest final release, optionally one tag per explicit LTS series."""
    mode = cfg.get('release_tracking', 'latest')
    if mode not in ('latest', 'latest_and_lts'):
        raise ValueError('release_tracking must be latest or latest_and_lts')
    lts = {str(x) for x in cfg.get('lts_series', [])} if mode == 'latest_and_lts' else set()
    tags = release_tags(repo, lts)
    selected = {tags[-1]['tag']: tags[-1]} if tags else {}
    for series in sorted(lts):
        matches = [t for t in tags if t['series'] == series]
        if matches:
            selected[matches[-1]['tag']] = matches[-1]
    result = sorted(selected.values(), key=lambda t: t['version'])
    policy = cfg.get('release_policy', {})
    scoped_policy = {**policy, 'series': {s:p for s,p in policy.get('series', {}).items()
                                          if s in {t['series'] for t in result}}}
    return result, scoped_policy


def release_status(repo,db,tags,shas):
    fingerprint=hashlib.sha256(json.dumps(tags,sort_keys=True).encode()).hexdigest(); out={}
    unique=sorted(set(shas)); progress=Progress('Commit release checks',len(unique)); hits=0
    cached_rows={sha:result for sha,result in db.execute('SELECT sha,result FROM release_cache WHERE fingerprint=?',(fingerprint,))}
    pending=set(unique)-cached_rows.keys()
    reachable=None
    # One graph walk rejects all commits unreachable from ANY stable tag. Most recent
    # main commits are in this category; only positive candidates require per-commit tag checks.
    if tags and len(pending)>=8:
        try:
            reachable=pending.intersection(repo.git('rev-list',*['refs/tags/'+t['tag'] for t in tags],'--').splitlines())
            logging.info('Release batch: %d of %d uncached commits reachable from any stable tag',len(reachable),len(pending))
        except RuntimeError:
            logging.warning('Release batch unavailable; using exact per-commit checks')
    for i,sha in enumerate(unique,1):
        progress.item(i,sha[:12])
        cached=cached_rows.get(sha)
        if cached is not None:
            out[sha]=json.loads(cached); hits+=1; progress.done(i); continue
        # A tag containing the exact commit is evidence of inclusion, not feature availability after reverts/backports.
        contained=set(repo.git('tag','--contains',sha,'--list',*[t['tag'] for t in tags]).splitlines()) if tags and (reachable is None or sha in reachable) else set()
        stable=[t for t in tags if t['tag'] in contained]; lts=[t for t in stable if t['lts']]
        result={'first_release':stable[0]['tag'] if stable else None,'latest_release':stable[-1]['tag'] if stable else None,
                'lts_tags':[t['tag'] for t in lts], 'status':'tagged' if stable else ('main_only' if tags else 'unknown')}
        out[sha]=result
        db.execute('INSERT OR REPLACE INTO release_cache VALUES(?,?,?)',(sha,fingerprint,json.dumps(result)))
        progress.done(i)
    db.commit(); logging.info('Release checks: %d cache hits, %d computed',hits,len(unique)-hits); return out


def get_prs(db,cfg,now):
    """Bounded public API snapshot; network failure preserves the previous snapshot and flags it stale."""
    pcfg=cfg.get('pull_requests',{}); key='pr_snapshot'; old=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
    if not pcfg.get('enabled',True) or cfg.get('upstream','https://github.com/zephyrproject-rtos/zephyr.git').rstrip('/').removesuffix('.git')!='https://github.com/zephyrproject-rtos/zephyr':
        return {'status':'disabled','items':[],'scanned':0}
    pages=max(1,min(10,int(pcfg.get('pages',2)))); items=[]; scanned=0; truncated=False
    try:
        for page in range(1,pages+1):
            logging.info('GitHub API: fetching PR page %d/%d',page,pages)
            url='https://api.github.com/repos/zephyrproject-rtos/zephyr/pulls?'+urlencode({'state':'open','base':cfg.get('branch','main'),'sort':'updated','direction':'desc','per_page':100,'page':page})
            headers={'Accept':'application/vnd.github+json','User-Agent':'zephyr-pulse/0.2'}
            if os.environ.get('GITHUB_TOKEN'): headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
            with urlopen(Request(url,headers=headers),timeout=15) as response:
                records=json.load(response); more='rel="next"' in response.headers.get('Link','')
            scanned+=len(records)
            for p in records:
                labels=[l['name'] for l in p.get('labels',[])]; text=p['title']+' '+' '.join(labels)
                if re.search(r'\b(board|boards|sensor|sensors|driver|drivers|soc|devicetree|dts|hardware|peripheral|gpio|uart|spi|i2c|adc|can|usb|ethernet|wifi|bluetooth)\b',text,re.I):
                    items.append({'number':int(p['number']),'title':p['title'],'updated':p['updated_at'],'draft':bool(p.get('draft')),'labels':labels})
            if not more: break
            if page==pages: truncated=True
        result={'status':'ok','updated':now.isoformat(),'items':list({p['number']:p for p in items}.values()),'scanned':scanned,'truncated':truncated}
        db.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(key,json.dumps(result))); db.commit(); return result
    except (OSError,ValueError,KeyError,TypeError) as e:
        logging.warning('PR snapshot unavailable: %s',type(e).__name__)
        result=json.loads(old[0]) if old else {'items':[],'scanned':0}; return {**result,'status':'stale' if old else 'unavailable'}


def render_extra(db,docs,now,head,boards,coverage,tags,prs,statuses,watch,site_url,hours=72,policy=None,preferences=None,snapshots=None):
    policy=policy or {}
    from comparison import comparison_data, canonical, FEATURES
    preferences=preferences or {}
    snapshots=snapshots or []
    from pulse import md, UPSTREAM, CATEGORIES, write_rss
    from html import escape
    docs.mkdir(parents=True,exist_ok=True); directory=docs/'boards'; directory.mkdir(exist_ok=True)
    expected_pages={b['slug']+'.md' for b in boards.values()}
    for p in directory.glob('*.md'):
        if p.name not in expected_pages: p.unlink()
    page_counts=Counter()
    stamp=f'Updated **{now:%Y-%m-%d %H:%M UTC}** · main snapshot `{head[:12]}`.\n\n'
    cov=f"History: **{coverage['processed']} / {coverage['total']}** first-parent commits processed in the last {coverage['days']} days. {'Complete.' if coverage['complete'] else 'Backfill in progress; counts are incomplete.'}"
    idx=folder_index(boards)
    rows=[dict(r) for r in db.execute('SELECT e.*,c.committed,c.subject AS commit_subject FROM events e JOIN commits c USING(sha) ORDER BY c.committed DESC,sha,kind,subject')]
    for r in rows:
        r['boards']=board_ids(r,boards,idx); r['release']=statuses.get(r['sha'],{}); r['watched']=watch_match(r,boards,watch)
    history=defaultdict(list)
    for r in db.execute('SELECT m.*,h.committed FROM milestones m JOIN history_seen h USING(sha) ORDER BY h.committed DESC,sha,kind,label,path'):
        history[r['board']].append(dict(r))
    def release_text(s):
        if s.get('first_release'):
            lts=s.get('lts_tags',[]); return f"Commit in {s['first_release']} · latest tracked containing tag {s['latest_release']}" + (f" · LTS-tagged: {', '.join(lts)}" if lts else '')
        return 'Not in tracked releases — exact commit' if s.get('status')=='main_only' else 'Release inclusion unknown'
    def commit_link(sha): return f'[{sha[:10]}]({UPSTREAM}/commit/{sha})'
    def source_link(sha,path): return f'[source]({UPSTREAM}/blob/{sha}/{quote(path,safe="/")})'
    def save(name,lines):
        path=docs/name
        content=('---\nhide:\n  - toc\n---\n\n'+'\n'.join(lines)+'\n').encode('utf-8')
        same=path.is_file() and path.read_bytes()==content
        if not same: path.write_bytes(content)
        if name.startswith('boards/'): page_counts['unchanged' if same else 'changed']+=1
    catalog=['# Board explorer','',stamp,cov,'','All discovered `board.yml` definitions, not only watched boards. The browser filter changes only this list. [Compare hardware targets](compare.md).' ,'', '<div id="pulse-board-filter"></div>','', '| Board | Vendor | SoCs | Last detected milestone |','|---|---|---|---|']
    board_data=[]
    progress=Progress('Board pages',len(boards))
    for i,(key,b) in enumerate(sorted(boards.items(),key=lambda x:x[1]['name'].casefold()),1):
        progress.item(i,key)
        timeline=history[key]; last=timeline[0]['committed'][:10] if timeline else '—'
        soc_links = ', '.join('[{}](boards.html?subject={})'.format(md(soc),quote(soc,safe='')) for soc in b['socs'])
        catalog.append(f"| [{md(b['name'])}](boards/{b['slug']}.md) | [{md(b['vendor_name'])}](vendors.html?vendor={quote(b['vendor'],safe='')}) | {soc_links} | {last} |")
        item={k:v for k,v in b.items() if k not in ('raw','metadata')}; item.update(last_activity=last,url='boards/'+b['slug']+'.html'); board_data.append(item)
        revision=b.get('evidence_revision',head)
        board_stamp=f'Hardware evidence snapshot: [`{revision[:12]}`]({UPSTREAM}/commit/{revision}). See [Board explorer](../boards.md) for latest collection time.'
        lines=[f"# {md(b['full_name'])}",'',board_stamp,f"**Board:** `{md(b['name'])}` · **Vendor:** {md(b['vendor_name'])} · **SoCs:** {md(', '.join(b['socs']) or 'Not declared')}",'',f"[Board source]({UPSTREAM}/tree/{revision}/{quote(b['folder'],safe='/')}) · {source_link(revision,b['source'])}",'',f'[Compare hardware](../compare.md) · [Related hardware / news](../hardware-search.html?subject={quote(b["name"],safe="")}) · <a href="../compare.html?board={quote(key,safe="")}">Choose a target from this board in comparator</a>','', '## Target capability matrix','', 'Exact-target YAML declarations and revision-pinned DTS source hints are separate evidence. Missing evidence is unknown, not unsupported. DTS hints do not resolve conditional includes, ancestor status, overlays or Kconfig. No builds or hardware tests performed.','']
        if b.get('doc_source'):
            doc=b['doc_source']; lines[lines.index('## Target capability matrix'):lines.index('## Target capability matrix')]=[f'[Official board documentation (latest; may differ from this snapshot)](https://docs.zephyrproject.org/latest/{quote(doc[:-4],safe="/")}.html) · {source_link(revision,doc)}','']
        for target in sorted(set(b['targets'])|set(b['metadata'])):
            meta=b['metadata'].get(target); lines += [f'### {md(target)}','']
            if not meta: lines += ['_No exact target YAML metadata found._','']; continue
            features={canonical(f) for f in meta['features']}
            lines += [f"Architecture: {md(meta['arch'] or 'not declared')} · RAM: {md(meta['ram'] if meta['ram'] is not None else 'not declared')} · Flash: {md(meta['flash'] if meta['flash'] is not None else 'not declared')} (upstream metadata, normally KiB). {source_link(revision,meta['path'])}",'','| Peripheral / feature | Evidence | Compatible / source |','|---|---|---|']
            ev=meta.get('dts_evidence',{}); hints=set(ev.get('features',[])); present=set(ev.get('present_features',[]))
            for f in sorted(features|hints|present):
                evidence=('Declared (YAML)' if f in features else 'DTS source hint' if f in hints else 'Present in DTS; no okay hint')
                matches=[n for n in ev.get('nodes',[]) if f in n['features']]
                by_compat={}
                for n in matches:
                    by_compat.setdefault(n['compatible'],n['binding_paths'][0] if n['binding_paths'] else n['compatible_paths'][0])
                refs=' · '.join(f'[{md(c)}]({UPSTREAM}/blob/{revision}/{quote(p,safe="/")})' for c,p in sorted(by_compat.items()))
                lines.append(f"| {md(f)} | {evidence} | {refs or '—'} |")
            if not features and not hints and not present: lines.append('| — | No evidence | — |')
            lines += ['', 'A missing row means no evidence was collected, not that the hardware is unsupported. Inspect source details for instance status and matching driver references.', '']
            if ev.get('entry'):
                lines += [f"Exact-target DTS: {source_link(revision,ev['entry'])}", '', '<details class="pulse-evidence"><summary>Inspect compatible strings, instances, bindings and source history</summary>', '<div class="pulse-matrix"><table><thead><tr><th>Peripheral</th><th>Compatible / node</th><th>Source status hint</th><th>Evidence</th></tr></thead><tbody>']
                for node in ev['nodes']:
                    paths=sorted(set(node['compatible_paths']+node['status_paths']+node['binding_paths']+node.get('driver_paths',[])))
                    refs='<br>'.join(f'<a href="{UPSTREAM}/blob/{revision}/{quote(p,safe="/")}">{escape(PurePosixPath(p).name)}</a> · <a href="{UPSTREAM}/commits/{revision}/{quote(p,safe="/")}">history</a>' for p in paths)
                    lines.append(f'<tr><td>{escape(", ".join(node["features"]))}</td><td><code>{escape(node["compatible"])}</code><br>{escape(node["node"])}</td><td>{escape(node["status"])} ({escape(", ".join(node["status_values"]) or "none")})</td><td>{refs}</td></tr>')
                lines += ['</tbody></table></div></details>','']
            lines += ['']
        if not b['targets'] and not b['metadata']: lines += ['_No target metadata found._','']
        lines += ['## Recent support timeline','',f"Retained board milestones (last {coverage['days']} days). [Global history coverage](../boards.md).",'','| UTC date | Signal | Evidence | Release inclusion |','|---|---|---|---|']
        for m in timeline:
            lines.append(f"| {m['committed'][:10]} | {md(m['label'])} ({md(m['confidence'])}) | {commit_link(m['sha'])} · {source_link(m['sha'],m['path'])} | {md(release_text(statuses.get(m['sha'],{})))} |")
        if not timeline: lines += ['| — | No retained milestone | — | — |']
        lines += ['','## Raw board-folder devicetree evidence','','These file-local declarations may apply to different variants or boards sharing the folder. Includes, overlays and Kconfig are not resolved.','','| File | Node | Explicit status | Compatible |','|---|---|---|---|']
        for r in b['raw']: lines.append(f"| {source_link(revision,r['path'])} ({md(PurePosixPath(r['path']).name)}) | {md(r['node'])} | {md(r['status'] or 'not explicit')} | {md(r['compatible'] or '—')} |")
        if not b['raw']: lines += ['| — | — | No local evidence | — |']
        save('boards/'+b['slug']+'.md',lines)
        progress.done(i)
    logging.info('Board Markdown: %d changed/new, %d unchanged',page_counts['changed'],page_counts['unchanged'])
    save('boards.md',catalog)
    vendor_rows=defaultdict(lambda:{'counts':Counter(),'authors':set(),'commits':set(),'days':Counter(),'last':'','activity_days':defaultdict(set)})
    for r in db.execute('SELECT a.*,h.committed FROM vendor_activity a JOIN history_seen h USING(sha)'):
        v=vendor_rows[r['vendor']]; v['counts'][r['signal']]+=1; v['authors'].add(r['author']); v['commits'].add(r['sha']); v['last']=max(v['last'],r['committed']); v['activity_days'][r['committed'][:10]].add(r['sha'])
    vendors=[]
    vendor_lines=['# Vendor activity','',stamp,cov,'','Counts are distinct commit/vendor/signal combinations, not devices shipped. Vendor refers to the affected hardware namespace, **not the contributor’s employer**. Fixes are title signals; test changes are source changes, not coverage or pass rates.','','<div id="pulse-vendor-filter"></div>','','| Vendor | Hardware commits | New-board signals | Capability signals | Driver / sensor introduction signals | Driver changes | Fix signals | Test-source signals | Distinct Git authors | Latest activity |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for name,v in sorted(vendor_rows.items(),key=lambda x:(-len(x[1]['commits']),x[0])):
        c=v['counts']; count=len(v['commits']); d={'vendor':name,'commits':count,'counts':dict(c),'authors':len(v['authors']),'last':v['last'],'daily':{day:len(shas) for day,shas in sorted(v['activity_days'].items())}}; vendors.append(d)
        vendor_lines.append(f"| [{md(name)}](boards.html?vendor={quote(name,safe='')}) | {count} | {c['board']} | {c['board_feature']} | {c['driver']+c['sensor']} | {c['driver_changes']} | {c['fix_signals']} | {c['test_source_changes']} | {d['authors']} | {v['last'][:10]} |")
    vendor_lines += ['','## Activity trends','','<div id="pulse-vendor-trends"></div>','','Missing days during backfill are not evidence of inactivity. Vendors absent from this table have no attributed signals in the processed history.']
    save('vendors.md',vendor_lines)
    release_lines=['# Release and LTS tracking','',stamp,'Only the latest stable release is tracked by default; optional configured LTS series contribute their latest final tag. Development .99 and release-candidate tags are excluded. Inclusion means the exact main commit is reachable from a tag; cherry-picked backports and later reversions are not detected. It does not certify hardware operation.','','[Official release support / EOL policy](https://docs.zephyrproject.org/latest/releases/index.html) · LTS series are configured in `config.yml`; verify their current support dates upstream.','','## Tracked release tags','', '| Tag | Tag creator date | Configured LTS series |','|---|---|---|']
    for t in reversed(tags): release_lines.append(f"| [{t['tag']}]({UPSTREAM}/releases/tag/{t['tag']}) | {md(t['date'][:10])} | {'Yes' if t['lts'] else '—'} |")
    if not tags: release_lines += ['| — | No eligible stable tags found | — |']
    release_lines += ['','## Configured support lifecycle','','Policy snapshot: '+md(policy.get('checked','not configured'))+'. Update this configuration from the official release page; the Git tags refresh automatically.','','| Series | Policy status | End of life |','|---|---|---|']
    for series,p in policy.get('series',{}).items():
        eol=str(p.get('eol','')); status=str(p.get('status','unknown'))
        if eol and eol<now.date().isoformat(): status='End of life'
        release_lines.append(f'| {md(series)} | {md(status)} | {md(eol or "not announced")} |')
    if not policy.get('series'): release_lines += ['| — | Not configured | — |']
    release_lines += ['','Planned releases are listed separately in the official policy; a plan does not imply a release exists.']
    release_lines += ['','## Recent hardware news: release inclusion','','| UTC date | Change | Release status | Commit |','|---|---|---|---|']
    for r in rows:
        if r['kind'] not in ('other','docs'): release_lines.append(f"| {r['committed'][:10]} | {md(r['subject'])} | {md(release_text(r['release']))} | {commit_link(r['sha'])} |")
    save('releases.md',release_lines)
    pr_lines=['# Upcoming hardware support','',stamp,'Open pull requests are proposals, **not merged or released support**. This optional GitHub API view scans recently updated PRs, matching hardware-related titles and labels; it is not an exhaustive roadmap.','',f"Snapshot status: **{md(prs['status'])}** · scanned {prs.get('scanned',0)} PRs · {'bounded / more pages available' if prs.get('truncated') else 'no additional pages reported'} · last successful refresh: {md(prs.get('updated','none'))}",'','| Updated UTC | Proposal | State | Labels |','|---|---|---|---|']
    for p in prs['items']: pr_lines.append(f"| {md(p['updated'][:10])} | [#{p['number']} — {md(p['title'])}]({UPSTREAM}/pull/{p['number']}) | {'Draft' if p['draft'] else 'Open'} | {md(', '.join(p['labels']))} |")
    if not prs['items']: pr_lines += ['| — | No matching proposals in snapshot | — | — |']
    save('upcoming.md',pr_lines)
    watched=[r for r in rows if r['watched']]
    watch_lines=['# Watchlist','',stamp,'The overview and general feeds always include all hardware news. This page is an additional personal view. Patterns are case-insensitive; plain text matches substrings, and glob patterns support `*`, `?`, `[abc]`. Any matching board, vendor or peripheral qualifies. Board names, SoCs and target identifiers are searched.','','<div id="pulse-watchlist"></div>','','The [public watchlist RSS](watchlist.xml) follows server defaults, not your personal preferences.','','<div id="pulse-watch-fallback">','<h2>Server-configured watchlist (no JavaScript fallback)</h2>']
    for r in watched: watch_lines.append(f"<p>{r['committed'][:10]} · <a href=\"{UPSTREAM}/commit/{r['sha']}\">{escape(r['subject'])}</a> — {escape(CATEGORIES[r['kind']])}</p>")
    if not watched: watch_lines+=['<p>No matching events.</p>']
    watch_lines+=['</div>']
    save('watchlist.md',watch_lines)
    save('compare.md',['# Hardware comparator','',stamp,'Compare exact board targets against your product requirements. Metadata is source evidence, not proof of working hardware. No builds are performed.','', '[Personal settings](settings.md) · [Board explorer](boards.md) · [Release policy](releases.md)','','<div id="pulse-comparator"></div>','','Without JavaScript, use the individual board profiles in the [board explorer](boards.md).'])
    save('settings.md',['# Personal settings','', 'Preferences are stored in this browser and override published defaults. They never filter global news or change server configuration. Export a JSON file to transfer settings between browsers or projects.','','<div id="pulse-settings"></div>','','The public watchlist RSS remains server-configured. Collector interval, retention, upstream, deployment credentials and release policy remain administrator settings.'])
    save('hardware-search.md',['# Hardware search','',stamp,'Search all exact board targets, recent events and upcoming PRs with case-insensitive terms or wildcards. This search uses the published JSON data independently of the static site generator.','', '<div id="pulse-hardware-search"></div>', '', 'Without JavaScript, use [Board explorer](boards.md), [All commits](all.md), [Upcoming PRs](upcoming.md) or the [JSON dataset](intelligence.json).'])
    comparison=comparison_data(boards,snapshots,history,vendors)
    write_rss(docs/'watchlist.xml',watched,site_url,'Zephyr Pulse — Watchlist')
    from browser_data import publish_catalog
    publish_catalog(docs, comparison, {'updated':now.isoformat(),'head':head,'coverage':coverage,'boards':board_data,'watchlist':watch,'vendors':vendors,'releases':tags,'release_policy':policy,'pull_requests':prs,'events':rows,'preferences':preferences})
    (docs/'events.json').write_text(json.dumps({'updated':now.isoformat(),'events':rows,'window_hours':hours},ensure_ascii=False),encoding='utf-8')
    # Add a second, independent watched-news section without filtering the original homepage.
    home=docs/'index.md'; body=home.read_text(); marker='## Priority highlights'
    snippet='## Watchlist highlights\n\n[Edit preferences](settings.md) · [All watched news](watchlist.md) · [Public watchlist RSS](watchlist.xml)\n\n<div id="pulse-home-watch" class="pulse-watch-panel"></div>\n\n<div id="pulse-home-fallback">\n' 
    from news_table import render_news_table
    snippet+=(render_news_table(watched[:8],statuses,boards,idx) if watched else '<p>No matching events in this window.</p>')+'\n'
    snippet+='</div>\n' 
    snippet+='\n'
    body=body.replace(marker,snippet+marker,1)
    home.write_text(body,encoding='utf-8')
