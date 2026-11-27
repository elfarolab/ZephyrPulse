#!/usr/bin/env python3
"""Collect upstream changes and render a rolling, evidence-based news site."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import json
import hashlib
import logging
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from html import escape
from urllib.parse import quote
from xml.etree import ElementTree as ET
from email.utils import format_datetime
import yaml
from progress import stage, Progress, elapsed
import time

ROOT = Path(__file__).resolve().parent
UPSTREAM = 'https://github.com/zephyrproject-rtos/zephyr'
CATEGORIES = {
    'board_feature': 'Board capability changes', 'board_candidate': 'Possible board support',
    'board': 'New boards', 'board_change': 'Board maintenance', 'soc': 'SoCs',
    'sensor': 'Sensors', 'driver': 'Drivers', 'dts': 'Devicetree', 'dt_bindings': 'DT bindings', 'subsys': 'Subsystems',
    'samples': 'Samples', 'tests': 'Tests', 'manifest': 'West manifest', 'kernel': 'Kernel & architecture', 'docs': 'Documentation', 'other': 'Other changes',
}
UTC = dt.timezone.utc

def run(*args, cwd=None, allow=(0,)):
    # Keep command stdout clean for parsers. Log only the operation, not credentials or URLs.
    operation = args[3] if args[:2] == ('git', '-C') else args[0]
    logging.debug('Running %s', operation)
    p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode not in allow:
        raise RuntimeError(f'{args[0]} exited {p.returncode}: {p.stderr.decode(errors="replace").strip()}')
    return p.stdout.decode('utf-8', errors='replace')

class Git:
    def __init__(self, path): self.path = Path(path)
    def git(self, *args, allow=(0,)): return run('git', '-C', str(self.path), *args, allow=allow)
    def fetch(self, url, branch, options=None, seed=None):
        from git_transport import synchronize
        return synchronize(self, url, branch, options, seed)
    def blob(self, sha, path):
        if not sha or not path: return ''
        return self.git('show', f'{sha}:{path}')
    def parent(self, sha):
        parents = self.git('show', '-s', '--format=%P', sha).split()
        return parents[0] if parents else None
    def changes(self, sha, parent):
        if parent: out = self.git('diff', '--name-status', '-z', '-M', parent, sha, '--')
        else: out = self.git('diff-tree', '--root', '-r', '--no-commit-id', '--name-status', '-z', sha)
        fields = iter(out.rstrip('\0').split('\0')) if out else iter([])
        for status in fields:
            path = next(fields)
            if status.startswith(('R','C')): yield status[0], path, next(fields)
            elif status.startswith('A'): yield 'A', None, path
            elif status.startswith('D'): yield 'D', path, None
            else: yield status[0], path, path
    def include_users(self, sha, path):
        name = PurePosixPath(path).name
        out = self.git("grep", "-l", "-F", "-e", name, sha, "--", "boards", "dts", "soc", allow=(0,1))
        for entry in out.splitlines():
            candidate = entry.split(":",1)[-1]
            if is_dts(candidate) and candidate != path:
                content = self.blob(sha,candidate)
                includes = re.findall(r'(?m)^\s*(?:#\s*include|/include/)\s*["<]([^">]+)[">]', content)
                if any(PurePosixPath(x).name == name for x in includes): yield candidate
    def grep_compat(self, sha, compatible):
        return self.git('grep', '-l', '-F', '-e', f'"{compatible}"', sha, '--', 'boards', 'dts', 'soc', allow=(0,1)).splitlines()

def yload(s):
    try:
        result = yaml.safe_load(s)
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError: return {}

def board_defs(s):
    d = yload(s); entries = d.get('boards', []) or []
    if isinstance(d.get('board'), dict): entries = [d['board']]
    return {str(b['name']): b for b in entries if isinstance(b, dict) and b.get('name')}

def soc_names(s):
    result = set()
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'socs' and isinstance(v,list):
                    result.update(str(x['name']) for x in v if isinstance(x,dict) and x.get('name'))
                walk(v)
        elif isinstance(obj,list):
            for x in obj: walk(x)
    walk(yload(s)); return result

def supported(s):
    d = yload(s); items = d.get('supported', []) or []
    return str(d.get('identifier', '')), {str(x) for x in items} if isinstance(items, list) else set()

def variants(defs):
    # Compare named SoCs and nested variant names without pretending to enumerate CPU clusters.
    result = set()
    def walk(items, prefix):
        for item in items or []:
            if isinstance(item, dict) and item.get('name'):
                key = prefix + '/' + str(item['name']); result.add(key)
                walk(item.get('variants', []), key)
    for name, board in defs.items():
        walk(board.get('socs', []), name); walk(board.get('variants', []), name)
    return result

def board_folder(path):
    p = PurePosixPath(path).parts
    if len(p) >= 4 and p[0] == 'boards' and p[1] not in ('shields','common','extensions'):
        return '/'.join(p[:3])
    return None

def is_dts(path): return path.endswith(('.dts','.dtsi','.overlay'))

# A lightweight lexical scanner, not a Zephyr devicetree compiler. Ignore braces in comments/strings.
TOKEN = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|[{};]|[^{};"/]+|/', re.S)
def nodes(source):
    stack = []; pending = ''; result = defaultdict(dict)
    for m in TOKEN.finditer(source):
        t = m.group()
        if t.startswith(('/*','//')): continue
        if t == '{':
            header = '\n'.join(x for x in pending.splitlines() if not x.lstrip().startswith('#')).strip()
            header = ' '.join(header.split()); pending = ''
            # Prefer node labels for stable identity, otherwise use node names.
            label = re.match(r'^([\w]+)\s*:', header)
            reference=re.match(r'^(?:[\w]+\s*:\s*)*(&[\w]+)$',header)
            name = reference.group(1) if reference else '&' + label.group(1) if label else header
            stack.append(name)
        elif t == '}':
            if stack: stack.pop()
            pending = ''
        elif t == ';':
            if stack:
                key = stack[-1] if stack[-1].startswith('&') else '/'.join(stack)
                for prop in ('status','compatible'):
                    match = re.match(r'^\s*'+prop+r'\s*=\s*(.*)$', pending, re.S)
                    if match: result[key][prop] = tuple(re.findall(r'"([^"\n]+)"', match.group(1)))
            pending = ''
        else: pending += t
    return dict(result)

def driver_tokens(source):
    return set(re.findall(r'^\s*#\s*define\s+DT_DRV_COMPAT\s+([a-zA-Z0-9_]+)\b', source, re.M))

def compat_token(compatible): return re.sub(r'[^A-Za-z0-9_]', '_', compatible).lower()

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS commits(sha TEXT PRIMARY KEY, committed TEXT NOT NULL, subject TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, sha TEXT NOT NULL REFERENCES commits(sha) ON DELETE CASCADE,
 kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL, confidence TEXT NOT NULL, path TEXT NOT NULL,
 UNIQUE(sha,kind,subject,detail,path));
CREATE INDEX IF NOT EXISTS events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS commits_time ON commits(committed);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
'''

def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path); db.row_factory = sqlite3.Row
    db.executescript(SCHEMA);
    from intelligence import SCHEMA as INTELLIGENCE_SCHEMA
    db.executescript(INTELLIGENCE_SCHEMA)
    # Additive migrations preserve the user's existing database and Git history.
    columns = {r[1] for r in db.execute('PRAGMA table_info(events)')}
    for name in ('change_type','source_revision'):
        if name not in columns: db.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    db.commit()
    return db

def classify(repo, sha, parent, changes, subject=None):
    from classification import supplement
    changes = list(changes)
    events = set(); new_tokens = {}; new_compat = {}; shared_changes = []
    def board_users(path):
        # Bounded basename-based reverse include walk; conditional includes and paths are unresolved.
        seen = {path}; frontier = [path]; found = {}
        for _ in range(5):
            next_frontier = []
            for current in frontier:
                for user in repo.include_users(sha,current):
                    if user in seen: continue
                    seen.add(user); folder = board_folder(user)
                    if folder: found.setdefault(folder,user)
                    next_frontier.append(user)
                    if len(seen) >= 150: return found
            frontier = next_frontier
            if not frontier: break
        return found
    def add(kind, subject, detail, path, confidence='observed'):
        events.add((kind,subject,detail,confidence,path))
    for status, oldpath, path in changes:
        if not path: continue
        p = PurePosixPath(path); folder = board_folder(path)
        if folder and p.name == 'board.yml':
            old = board_defs(repo.blob(parent, oldpath)); new = board_defs(repo.blob(sha, path))
            for name in new.keys() - old.keys():
                add('board',name,'New board name in board.yml.',path)
            for v in variants(new)-variants(old):
                if v.split('/')[0] in old:
                    add('board_feature',v,'New SoC or variant in existing board metadata.',path)
        if folder and p.suffix == '.yaml' and p.name != 'board.yml':
            target, after = supported(repo.blob(sha,path)); _, before = supported(repo.blob(parent,oldpath))
            if target and status != 'A':
                for feature in after-before:
                    add('board_feature',target,'New supported metadata entry: '+feature,path)
            elif target and status == 'A' and after:
                add('board_candidate',target,'New target metadata declares: '+', '.join(sorted(after)),path,'candidate')
        if folder and (p.name.endswith('_defconfig') or p.suffix == '.conf') and status != 'A':
            def enabled(text): return set(re.findall(r'^\s*(CONFIG_[A-Z0-9_]+)=y\s*$',text,re.M))
            for symbol in enabled(repo.blob(sha,path))-enabled(repo.blob(parent,oldpath)):
                add('board_candidate',folder,'New enabled Kconfig assignment: '+symbol+'; may not be a hardware capability.',path,'candidate')
        if is_dts(path) and path.startswith(('boards/','dts/','soc/')):
            old = nodes(repo.blob(parent,oldpath)); new = nodes(repo.blob(sha,path))
            for key, props in new.items():
                prev = old.get(key,{})
                if props.get('status') == ('okay',) and prev.get('status') != ('okay',):
                    label = folder or str(p.parent)
                    explicit = prev.get('status') == ('disabled',)
                    kind = 'board_feature' if folder and explicit else 'board_candidate' if folder else 'dts'
                    if explicit and not folder: shared_changes.append((path,key))
                    if status != 'A' or folder is None:
                        add(kind,label, f'{key}: '+('explicit disabled → okay' if explicit else 'explicit status okay added')+' (source only).',path,'observed' if explicit else 'candidate')
                if folder and status != 'A' and props.get('compatible') and props.get('compatible') != prev.get('compatible'):
                    add('board_candidate',folder,f'{key}: compatible changed to '+', '.join(props['compatible']),path,'candidate')
            if status == 'A': add('dts',p.name,'New devicetree source file.',path)
            elif not any(e[4] == path for e in events): add('dts',p.name,'Devicetree source modified.',path)
        if path.startswith('dts/bindings/') and p.suffix in ('.yaml','.yml'):
            old = yload(repo.blob(parent,oldpath)); new = yload(repo.blob(sha,path)); compat = new.get('compatible')
            if isinstance(compat,str) and compat != old.get('compatible'):
                add('dt_bindings',compat,'New or changed devicetree binding compatible.',path)
                new_compat[compat] = path
                if '/sensor/' in path: add('sensor',compat,'Sensor binding introduced; does not prove a driver exists.',path,'candidate')
        if path.startswith('drivers/') and p.suffix in ('.c','.cpp'):
            before = driver_tokens(repo.blob(parent,oldpath)); after = driver_tokens(repo.blob(sha,path)); kind = 'sensor' if path.startswith('drivers/sensor/') else 'driver'
            for token in after-before:
                add(kind,token,'New DT_DRV_COMPAT declaration in driver source.',path)
                new_tokens[token] = path
            if status == 'A' and not (after-before):
                add(kind,p.name,'New implementation file; may be a refactor or helper.',path,'candidate')
        if path.startswith('soc/') and p.name == 'soc.yml':
            before = repo.blob(parent,oldpath); after = repo.blob(sha,path)
            added = soc_names(after)-soc_names(before)
            for name in added: add('soc',name,'New SoC name in SoC metadata.',path)
            if not added and status == 'A': add('soc',str(p.parent),'New SoC metadata file.',path,'candidate')
            elif not added and before != after: add('soc',str(p.parent),'SoC metadata changed.',path,'candidate')
        if status == 'A' and p.suffix in ('.rst','.md') and (path.startswith('doc/') or (folder and '/doc/' in path)):
            add('docs',p.stem,'New documentation source page.',path)
    # Find DTS compatible strings for newly introduced driver tokens, including existing bindings.
    # Search binding YAML only when driver tokens appeared.
    if new_tokens:
        found = repo.git('grep','-h','-E',r'^[[:space:]]*compatible:[[:space:]]*',sha,'--','dts/bindings',allow=(0,1))
        for line in found.splitlines():
            value = line.split(':',1)[1].split('#',1)[0].strip().strip('"\'')
            if compat_token(value) in new_tokens: new_compat.setdefault(value, new_tokens[compat_token(value)])
    if new_tokens:
        declarations=repo.git('grep','-h','-E',r'compatible[[:space:]]*=',sha,'--','boards','dts','soc',allow=(0,1))
        for line in declarations.splitlines():
            for value in re.findall(r'"([^"\n]+)"',line.split('compatible',1)[-1]):
                if compat_token(value) in new_tokens: new_compat.setdefault(value,new_tokens[compat_token(value)])
    for path,key in shared_changes:
        for folder,user in board_users(path).items():
            add('board_candidate',folder,f'Shared DTS {path}: {key} disabled → okay; possible include chain via {user}.',user,'candidate')
    for compat, binding_path in new_compat.items():
        token = compat_token(compat)
        if token not in new_tokens: continue  # Binding alone is not a driver introduction.
        for match in repo.grep_compat(sha,compat):
            path = match.split(':',1)[-1]; folder = board_folder(path)
            if folder and is_dts(path):
                add('board_candidate',folder,f'New driver compatible {compat} is referenced by board source; driver: {new_tokens[token]}. Verify effective DTS and build.',path,'candidate')
            elif is_dts(path):
                users = board_users(path)
                for affected,user in users.items():
                    add('board_candidate',affected,f'New driver {compat}; possible shared DTS include chain from {path}. Driver: {new_tokens[token]}. Verify build.',user,'candidate')
                if not users: add('board_candidate',str(PurePosixPath(path).parent),f'New driver {compat} matches shared DTS source; affected boards not resolved.',path,'candidate')
    if subject is None: subject = repo.git('show','-s','--format=%s',sha).strip()
    return supplement(repo,sha,parent,changes,subject,events)


def first_parent_window(repo, head, cutoff):
    """Return newest-first first-parent commits at/after cutoff, even with skewed dates.

    Use a single local metadata walk rather than the newer --since-as-filter
    option. Do not stop at an old commit: its parent can have a newer timestamp.
    """
    threshold = dt.datetime.fromisoformat(cutoff).timestamp()
    raw = repo.git('log', '--first-parent', '--no-show-signature', '--no-notes',
                   '--format=%H%x09%ct%x09%ae', head, '--')
    rows = []
    for line in raw.splitlines():
        sha, stamp, author = line.split('\t', 2)
        seconds = int(stamp)
        if seconds >= threshold:
            date = dt.datetime.fromtimestamp(seconds, UTC).isoformat(timespec='seconds')
            rows.append((sha, date, author))
    logging.debug('First-parent date window: %d matching commits since %s', len(rows), cutoff)
    return rows


def collect(db, repo, head, now, hours):
    cutoff = (now-dt.timedelta(hours=hours)).isoformat(timespec='seconds')
    prior = db.execute("SELECT value FROM state WHERE key='head'").fetchone()
    # On a rewritten branch, rebuild the window rather than silently retain orphan commits.
    from classification import VERSION as classifier_version, change_type
    version = db.execute("SELECT value FROM state WHERE key='news_classifier_version'").fetchone()
    reclassify = not version or version[0] != classifier_version
    rebuild = False
    if prior and prior[0] != head:
        # --is-ancestor alone accepts a side parent; check the first-parent boundary with range.
        history = repo.git('rev-list','--first-parent',head).splitlines()
        rebuild = prior[0] not in history
    if not prior or rebuild or reclassify:
        shas = [sha for sha, _, _ in reversed(first_parent_window(repo, head, cutoff))]
    else:
        shas = repo.git('rev-list','--first-parent','--reverse',f'{prior[0]}..{head}').splitlines()
    logging.info('Recent news: %s; cutoff %s', 'classifier migration' if reclassify and prior else ('history rewrite' if rebuild else ('incremental update' if prior else 'initial collection')), cutoff)
    progress=Progress('Recent commits', len(shas))
    with db:
        if rebuild or reclassify: db.execute('DELETE FROM commits')
        for i, sha in enumerate(shas, 1):
            progress.item(i, sha[:12])
            raw = repo.git('show','-s','--format=%cI%x00%s',sha).rstrip('\n'); date, subject = raw.split('\0',1)
            committed = dt.datetime.fromisoformat(date).astimezone(UTC).isoformat(timespec='seconds')
            if committed < cutoff or db.execute('SELECT 1 FROM commits WHERE sha=?',(sha,)).fetchone():
                progress.done(i); continue
            parent = repo.parent(sha); changes = list(repo.changes(sha,parent))
            events = classify(repo,sha,parent,changes,subject)
            db.execute('INSERT INTO commits VALUES(?,?,?)',(sha,committed,subject))
            deleted = {old for status,old,new in changes if status=='D'}
            db.executemany('INSERT OR IGNORE INTO events(sha,kind,subject,detail,confidence,path,change_type,source_revision) VALUES(?,?,?,?,?,?,?,?)', [(sha,*e,change_type(e[2]),(parent if e[4] in deleted else sha) if e[4] else '') for e in events])
            progress.done(i)
        db.execute('DELETE FROM commits WHERE committed < ?', (cutoff,))
        db.execute("INSERT OR REPLACE INTO state VALUES('news_classifier_version',?)",(classifier_version,))
        db.execute("INSERT INTO state VALUES('head',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(head,))
    logging.info('SQLite committed: %d retained commits, %d events; tracking %s',db.execute('SELECT count(*) FROM commits').fetchone()[0],db.execute('SELECT count(*) FROM events').fetchone()[0],head[:12])


def md(s):
    # HTML escape plus escape Markdown punctuation; do not allow upstream text to inject links/HTML.
    return re.sub(r'([\\`*_\[\]#|!~])',r'\\\1',escape(' '.join(str(s).split()),quote=False))

CATEGORY_ICONS = {'board_feature':'capability', 'board_candidate':'candidate', 'board':'board', 'board_change':'board', 'sensor':'sensor', 'driver':'driver', 'soc':'cpu', 'dts':'dts', 'dt_bindings':'bindings', 'subsys':'subsys', 'samples':'samples', 'tests':'tests', 'manifest':'manifest', 'kernel':'kernel', 'docs':'docs', 'other':'news'}

# Raw classifier categories are distinct from the 15 public dashboard views.
DISPLAY_CATEGORIES = {k:v for k,v in CATEGORIES.items() if k != 'board_candidate'}

def icon(name):
    # Names are application constants, not upstream text. CSS masks are decorative.
    return f'<span class="pulse-icon pulse-i-{escape(name, quote=True)}" aria-hidden="true"></span>'

def render(db, docs, now, hours, site_url, statuses=None, boards=None, dynamic_news=False, commit_files=None):
    from intelligence import board_ids, folder_index
    statuses = statuses or {}; boards=boards or {}; idx=folder_index(boards)
    docs.mkdir(parents=True,exist_ok=True)
    rows = db.execute('SELECT e.*,c.committed,c.subject AS commit_subject FROM events e JOIN commits c USING(sha) ORDER BY c.committed DESC,sha,kind,subject').fetchall()
    counts = defaultdict(int)
    for r in rows: counts[r['kind']]+=1
    header = f'Updated **{now:%Y-%m-%d %H:%M UTC}** · rolling {hours} hours · upstream Git\n\n'
    front='---\nhide:\n  - toc\n---\n\n'
    from news_table import render_news_table, subject_categories, render_grouped_news
    from news_groups import GROUPED, group_events, group_unit
    by_category={k:[r for r in rows if r['kind']==k] for k in CATEGORIES}
    by_category['board_feature'] = [r for r in rows if r['kind'] in ('board_feature','board_candidate')]
    counts['board_feature'] = len(by_category['board_feature'])
    group_counts={k:len(group_events(by_category[k], k)) for k in GROUPED}
    related = subject_categories(rows)
    home=[front.replace('  - toc','  - toc\n  - navigation')+'# Zephyr Pulse','',header,'<div class="pulse-stats">']
    for k,v in DISPLAY_CATEGORIES.items():
        unit = group_unit(k) if k in GROUPED else 'events'
        count = group_counts.get(k, counts[k])
        home.append(f'<a href="{k}.html" class="pulse-cat-{k}" title="{count} {unit} · {counts[k]} classified events"><span class="pulse-stat-top"><span class="pulse-stat-symbol">{icon(CATEGORY_ICONS[k])}</span>{icon("arrow")}</span><span class="pulse-stat-count"><strong>{count}</strong> <small class="pulse-stat-unit">{unit}</small></span><span class="pulse-stat-label">{escape(v)}</span></a>')
    home += ['</div>','','<div class="pulse-tools">']
    for href,label,ico in [('compare','Compare hardware','compare'),('hardware-search','Hardware search','search'),('boards','Board explorer','board'),('settings','Settings','settings')]:
        home.append(f'<a href="{href}.html">{icon(ico)} {label}</a>')
    home += ['</div>','','<!-- pulse-watchlist-slot -->','','[All commits](all.md) · [RSS feed](feed.xml) · [JSON feed](events.json)']
    (docs/'index.md').write_text('\n'.join(home))
    for k,v in DISPLAY_CATEGORIES.items():
        content = (f'<div data-pulse-category="{k}"></div>\n\n[Raw news JSON](events.json) · [All commits](all.md)' if dynamic_news else (render_grouped_news(by_category[k], k, statuses, boards, idx, commit_files) if k in GROUPED else render_news_table(by_category[k], statuses, boards, idx, related, category=k)))
        unit = group_unit(k)
        summary = f'{group_counts[k]} {unit} · {counts[k]} classified events' if k in GROUPED else f'{counts[k]} events'
        note = ''
        (docs/f'{k}.md').write_text(front+f'# {v}\n\n'+header+note+summary+' · newest first.\n\n'+content)
    (docs/'board_candidate.md').write_text(front+'# Board capability changes\n\nPossible board support is now included in [Board capability changes](board_feature.md).\n\n<div data-pulse-legacy-board-candidate></div>\n')
    if dynamic_news:
        fallback = ['<noscript><ul>']
        for r in db.execute('SELECT * FROM commits ORDER BY committed DESC,sha'):
            fallback.append(f'<li>{escape(r["committed"][:16].replace("T"," "))} UTC · <a href="{UPSTREAM}/commit/{r["sha"]}">{escape(r["subject"])}</a></li>')
        fallback.append('</ul></noscript>')
        all_content = '<div data-pulse-category="all"></div>\n\n[Raw news JSON](events.json)\n\n'+'\n'.join(fallback)
    else:
        all_content = render_grouped_news(rows, 'all', statuses, boards, idx, commit_files)
    (docs/'all.md').write_text(front+'# All commits\n\n'+header+all_content)
    (docs/'events.json').write_text(json.dumps({'updated':now.isoformat(),'window_hours':hours,'events':[dict(r) for r in rows]},indent=2,ensure_ascii=False))
    write_rss(docs/'feed.xml',rows,site_url)

def write_rss(path,rows,site_url,title='Zephyr Pulse'):
    rss=ET.Element('rss',version='2.0'); channel=ET.SubElement(rss,'channel')
    for k,v in [('title',title),('link',site_url),('description','Zephyr hardware support news')]: ET.SubElement(channel,k).text=v
    for r in rows:
        if r['kind']=='other': continue
        item=ET.SubElement(channel,'item')
        for k,v in [('title',r['subject']+' — '+CATEGORIES[r['kind']]),('link',UPSTREAM+'/commit/'+r['sha']),('description',escape(r['detail'])),('pubDate',format_datetime(dt.datetime.fromisoformat(r['committed']))),('guid',hashlib.sha256(json.dumps([r[k] for k in ('sha','kind','subject','detail','path')]).encode()).hexdigest())]:
            element=ET.SubElement(item,k,{'isPermaLink':'false'} if k=='guid' else {}); element.text=v
    ET.ElementTree(rss).write(path,encoding='utf-8',xml_declaration=True)


def remove_legacy_logo(docs):
    """Remove only the obsolete generated upstream branding asset."""
    (docs/'assets'/'zephyr-upstream.svg').unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='Override public config.yml (default: config.local.yml if present)')
    parser.add_argument('--git-seed', type=Path, help='Reuse full history from an existing local Zephyr repository on first sync')
    parser.add_argument('--no-publish',action='store_true')
    parser.add_argument('--no-build',action='store_true')
    parser.add_argument('--history-backfill',action='store_true',help='Process all remaining historical commits in this run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show individual commit and Git operation diagnostics')
    args=parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format='%(asctime)s %(levelname)-7s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
    started=time.monotonic()
    logging.info('Zephyr Pulse %s starting (PID %d)', (ROOT/'VERSION').read_text().strip(), os.getpid())
    logging.info('Git version: %s', run('git', '--version').strip())
    from configuration import load_config
    logging.info('Reading configuration: config.yml + %s', args.config or (ROOT/'config.local.yml' if (ROOT/'config.local.yml').exists() else 'no local overrides'))
    cfg=load_config(ROOT,args.config); state=ROOT/cfg.get('state_dir','state'); state.mkdir(parents=True,exist_ok=True)
    logging.info('State: %s; branch: %s; news: %sh; history: %sd',state,cfg.get('branch','main'),cfg.get('window_hours',72),cfg.get('history_days',90))
    logging.info('Build: %s; publish: %s',not args.no_build,bool(cfg.get('publish',False) and not args.no_publish and not args.no_build))
    with (state/'run.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: logging.info('Already running; skipping'); return
        repo=Git(state/'zephyr.git')
        with stage('Synchronize upstream Git'):
            head=repo.fetch(cfg.get('upstream',UPSTREAM+'.git'),cfg.get('branch','main'),cfg.get('git_transport',{}),args.git_seed)
        logging.info('Upstream HEAD: %s',head)
        now=dt.datetime.now(UTC)
        with stage('Open SQLite database'):
            db = connect(state/'pulse.sqlite3')
        try:
            with stage('Collect recent news'):
                collect(db,repo,head,now,int(cfg.get('window_hours',72)))
            from intelligence import inventory, update_history, tracked_releases, release_status, get_prs, render_extra
            with stage('Build board inventory'):
                boards=inventory(repo,head,db)
                logging.info('Inventory: %d boards',len(boards))
            with stage('Update historical intelligence'):
                coverage=update_history(db,repo,head,now,boards,int(cfg.get('history_days',90)),0 if args.history_backfill else int(cfg.get('history_batch',250)))
            with stage('Check release inclusion'):
                tags,policy=tracked_releases(repo,cfg)
                logging.info('Tracked release tags: %s', ', '.join(t['tag'] for t in tags) or 'none')
                shas=[r[0] for r in db.execute('SELECT sha FROM commits UNION SELECT sha FROM milestones')]
                logging.info('Release inclusion: %d tracked stable tags, %d commits to check (including cached results)',len(tags),len(shas))
                statuses=release_status(repo,db,tags,shas)
            from comparison import release_snapshots
            with stage('Read release board snapshots'):
                snapshots=release_snapshots(repo,tags,boards,policy,now,db)
            with stage('Refresh upcoming pull requests'):
                prs=get_prs(db,cfg,now)
                logging.info('PR snapshot: %s; %d scanned, %d matched',prs['status'],prs.get('scanned',0),len(prs['items']))
            site_url=cfg.get('site_url','http://localhost:8000/')
            with stage('Remove obsolete upstream branding'):
                remove_legacy_logo(ROOT/'docs')
            with stage('Generate recent news Markdown and feeds'):
                from news_groups import recent_files
                commit_files=recent_files(db,repo)
                render(db,ROOT/'docs',now,int(cfg.get('window_hours',72)),site_url,statuses,boards,dynamic_news=not cfg.get('generator',{}).get('native_search',False),commit_files=commit_files)
            from board_images import publish as publish_board_images
            with stage('Discover and publish board images'):
                board_images=publish_board_images(repo,head,boards,ROOT/'docs',cfg.get('board_images',True))
            with stage('Generate board pages, JSON and intelligence feeds'):
                render_extra(db,ROOT/'docs',now,head,boards,coverage,tags,prs,statuses,cfg.get('watchlist',{}),site_url,int(cfg.get('window_hours',72)),policy,cfg.get('preferences',{}),snapshots,board_images=board_images,commit_files=commit_files,dynamic_news=not cfg.get('generator',{}).get('native_search',False))
        finally:
            db.close()
        if not args.no_build:
            from generators import get_generator, build_site
            with stage('Build and validate static website'):
                build_site(ROOT, get_generator(cfg.get('generator', {})), site_url)
            logging.info('Static website ready: %s',ROOT/'site')
            if cfg.get('publish',False) and not args.no_publish:
                with stage('Publish to Cloudflare R2'):
                    subprocess.run(['bash',str(ROOT/'deploy/publish.sh')],cwd=ROOT,check=True)
            else: logging.info('Publishing skipped (disabled by configuration or --no-publish)')
        else: logging.info('Website build and publishing skipped (--no-build)')
    logging.info('Zephyr Pulse finished successfully in %s',elapsed(time.monotonic()-started))

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.warning('Collection interrupted by user')
        sys.exit(130)
    except Exception:
        logging.exception('Zephyr Pulse failed')
        sys.exit(1)
