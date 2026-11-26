"""Source-only exact-target comparison. No compilation or hardware claims."""
import logging
from progress import stage, Progress

# Conservative aliases: never infer CAN FD from CAN, USB host from USB, etc.
ALIASES = {'wdt':'watchdog', 'eth':'ethernet', 'netif:eth':'ethernet',
           'netif:wifi':'wifi', 'netif:bt':'bluetooth', 'bt':'bluetooth',
           'ble':'bluetooth-le', 'canfd':'can-fd', 'usb_device':'usb-device',
           'usbd':'usb-device', 'usb_host':'usb-host', 'pm':'power-management'}
FEATURES = ['gpio','uart','i2c','spi','adc','dac','pwm','can','can-fd','watchdog',
            'counter','rtc','usb','usb-device','usb-host','ethernet','wifi','bluetooth',
            'bluetooth-le','i2s','pdm','dma','flash','sdhc','display','sensor','crypto',
            'power-management','low-power','rng']

def canonical(value):
    value=str(value).strip().lower()
    return ALIASES.get(value,value)

def target_metadata(meta):
    if meta is None: return None
    return {'features': sorted({canonical(f) for f in meta['features']}),
            'raw_features': sorted(meta['features']), 'dts_evidence':meta.get('dts_evidence',{}), 'source_features':meta.get('dts_evidence',{}).get('features',[]), 'arch':meta['arch'],
            'ram':meta['ram'], 'flash':meta['flash'], 'path':meta['path']}

def release_snapshots(repo, tags, boards, policy, now, db=None):
    """Latest stable and latest patch in each configured LTS series.

    Compare current exact metadata paths/identifiers at tags. No inference from
    ancestry or old layouts; absent metadata is explicitly unknown.
    """
    from intelligence import blobs
    from performance import load, save
    from pulse import supported
    selected={}
    if tags: selected[tags[-1]['tag']]={**tags[-1], 'latest_stable':True}
    for t in tags:
        if t['lts']:
            # sorted ascending, last tag for each series wins
            selected_series=t['series']
            previous=next((k for k,v in selected.items() if v.get('lts_snapshot') and v['series']==selected_series),None)
            if previous and not selected[previous].get('latest_stable'): del selected[previous]
            selected[t['tag']]={**selected.get(t['tag'],t),'lts_snapshot':True}
    wanted={m['path'] for b in boards.values() for m in b['metadata'].values()}
    snapshots=[]
    progress=Progress('Release board snapshots',len(selected))
    for i,(tag,t) in enumerate(sorted(selected.items(),key=lambda x:x[1]['version'],reverse=True),1):
        logging.info('Release snapshot %d/%d: %s',i,len(selected),tag)
        key='release-snapshot:'+tag
        old=load(db,key) or {}
        cached=old.get('paths',{}) if old.get('object')==t['object'] else {}
        missing=wanted-cached.keys()
        logging.info('Release snapshot %s: %d cached paths, %d paths to check',tag,len(wanted)-len(missing),len(missing))
        if missing:
            with stage(f'Read uncached board metadata at {tag}'):
                files=set(repo.git('ls-tree','-r','--name-only',tag,'--','boards').splitlines())
                raw=blobs(repo,tag,sorted(missing & files))
            from hardware_evidence import EvidenceIndex
            from pulse import yload
            from pathlib import PurePosixPath
            evidence_index=EvidenceIndex(repo,tag) if raw else None
            for path in sorted(missing):
                cached[path]=None  # Cache absence as well as positive evidence.
                if path not in raw: continue
                source=raw[path]
                ident,features=supported(source)
                if ident:
                    ev=evidence_index.target(str(PurePosixPath(path).parent),ident,str(yload(source).get('arch','')),path)
                    cached[path]={'target':ident,'features':sorted({canonical(f) for f in features}),'source_features':ev['features'],'dts_evidence':ev}
            save(db,key,{'object':t['object'],'paths':cached})
        found={p:cached[p] for p in sorted(wanted) if cached.get(p) is not None}
        p=policy.get('series',{}).get(t['series'],{}); eol=str(p.get('eol',''))
        lifecycle=('End of life per configured policy' if eol and eol<now.date().isoformat() else str(p.get('status','Policy not configured')))
        snapshots.append({'tag':tag,'series':t['series'],'lts':t['lts'],'latest_stable':t.get('latest_stable',False),
                          'lifecycle':lifecycle,'eol':eol,'paths':found})
        progress.done(i)
    if db is not None:
        db.execute('CREATE TABLE IF NOT EXISTS performance_cache (key TEXT PRIMARY KEY, version TEXT NOT NULL, payload TEXT NOT NULL)')
        keys=[r[0] for r in db.execute("SELECT key FROM performance_cache WHERE key LIKE 'release-snapshot:%'")]
        db.executemany('DELETE FROM performance_cache WHERE key=?',[(k,) for k in keys if k.removeprefix('release-snapshot:') not in selected])
        db.commit()
    return snapshots

def comparison_data(boards, snapshots, history, vendors):
    result=[]; features=set(FEATURES); by_vendor={v['vendor']:v for v in vendors}
    for key,b in sorted(boards.items()):
        timeline=history.get(key,[]); vendor=by_vendor.get(b['vendor'],{})
        # Only exact board target identifiers, not a union across CPUs/variants.
        for target in sorted(set(b['targets'])|set(b['metadata'])) or [b['name']]:
            meta=target_metadata(b['metadata'].get(target)); releases=[]
            if meta: features.update(meta['features']); features.update(meta['source_features'])
            for s in snapshots:
                match=s['paths'].get(meta['path']) if meta else None
                found=match is not None and match['target']==target
                releases.append({'tag':s['tag'],'found':found,'features':match['features'] if found else None,
                                 'path':meta['path'] if found else None,'source_features':match['source_features'] if found else [],'dts_evidence':match['dts_evidence'] if found else {}})
                if found: features.update(match['features']); features.update(match['source_features'])
            result.append({'id':key+'::'+target,'board_id':key,'board':b['name'],'name':b['full_name'],
                           'vendor':b['vendor'],'vendor_name':b['vendor_name'],'socs':b['socs'], 'target':target,
                           'url':'boards/'+b['slug']+'.html','metadata':meta,'releases':releases,'evidence_revision':b.get('evidence_revision'),
                           'last_milestone':timeline[0]['committed'] if timeline else None,
                           'milestone_count':len(timeline),'vendor_commits':vendor.get('commits'),
                           'vendor_last':vendor.get('last')})
    return {'targets':result,'features':sorted(features),'snapshots':[{k:v for k,v in s.items() if k!='paths'} for s in snapshots]}
