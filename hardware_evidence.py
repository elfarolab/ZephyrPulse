"""Conservative, revision-pinned DTS source evidence; not an effective DT compiler.

Read only tracked blobs. Match literal includes and exact target filenames. A
source hint is deliberately not a support claim: CPP conditions, parent state,
macros, overlays and Kconfig are not evaluated. No upstream code is executed.
"""
from collections import defaultdict
from pathlib import PurePosixPath
import posixpath
import re
from performance import digest, trees

INCLUDE = re.compile(r'^\s*(?:#\s*include|/include/)\s*(["<])([^">]+)[">]', re.M)
COMMENTS = re.compile(r'/\*.*?\*/|//[^\n]*', re.S)
# Explicit subtype mappings, not guessed from a generic CAN declaration.
SPECIAL = {'nxp,flexcan-fd': ('can','can-fd'), 'bosch,m-can': ('can','can-fd'),
           'nxp,els': ('crypto',), 'nxp,els-trng': ('rng',),
           'nxp,kinetis-usbd': ('usb','usb-device'), 'nxp,ehci': ('usb','usb-device')}
# Only unambiguous binding families; a USB PHY alone doesn't imply a controller.
FAMILIES = {'adc':'adc','dac':'dac','can':'can','crypto':'crypto','dma':'dma',
            'ethernet':'ethernet','gpio':'gpio','i2c':'i2c','i2s':'i2s','pwm':'pwm',
            'rtc':'rtc','sensor':'sensor','serial':'uart','spi':'spi','watchdog':'watchdog',
            'rng':'rng','entropy':'rng','sdhc':'sdhc','counter':'counter','display':'display',
            'comparator':'comparator','i3c':'i3c','crc':'crc','opamp':'opamp','video':'video','edac':'edac','mbox':'mailbox','pdm':'pdm'}

class EvidenceIndex:
    def __init__(self, repo, ref, previous=None, object_ids=None):
        from intelligence import blobs
        self.ids = object_ids if object_ids is not None else trees(repo, ref, ['boards','dts','soc','include','drivers'])
        self.previous = previous or {}
        self.results = {}
        self.hits = self.misses = 0
        paths = sorted(p for p in self.ids if p.startswith(('boards/','dts/','soc/','include/')))
        selected = [p for p in paths if p.endswith(('.dts','.dtsi')) or (p.startswith('dts/bindings/') and p.endswith(('.yaml','.yml')))]
        self.data = blobs(repo, ref, selected)
        self.cache = {}
        self.drivers = defaultdict(set)
        matches=repo.git('grep','-n','-E',r'^[[:space:]]*#[[:space:]]*define[[:space:]]+DT_DRV_COMPAT[[:space:]]+[[:alnum:]_]+',ref,'--','drivers',allow=(0,1))
        for line in matches.splitlines():
            fields=line.split(':',3)
            if len(fields)!=4: continue
            m=re.search(r'\bDT_DRV_COMPAT\s+([A-Za-z0-9_]+)',fields[3])
            if m: self.drivers[m[1]].add(fields[1])
        self.bindings = defaultdict(list)
        # Read compatible only, no YAML include execution.
        for p,s in self.data.items():
            if not p.startswith('dts/bindings/') or not p.endswith(('.yaml','.yml')): continue
            m = re.search(r'^compatible:\s*["\']?([^\s"\'#]+)',s,re.M)
            if m: self.bindings[m[1]].append(p)

    def resolve(self, path, style, name, arch):
        roots = [posixpath.dirname(path)] if style=='"' else []
        roots += ['dts/'+arch] if arch else []
        roots += ['dts','dts/common','include','include/zephyr']
        for root in roots:
            p=posixpath.normpath(posixpath.join(root,name))
            if p in self.data: return p
        # No guessing based on basename or cross-architecture files.
        return None

    def parsed(self, path):
        from pulse import nodes
        if path not in self.cache:
            text=COMMENTS.sub('',self.data[path]); self.cache[path]=(INCLUDE.findall(text),nodes(text))
        return self.cache[path]

    def dependency_fingerprint(self, deps, includes, compats, arch):
        # Includes which used to be unresolved can become resolvable, or a
        # higher-priority include may appear. Recheck resolution, not just files.
        resolved = [(p, style, name, self.resolve(p, style, name, arch))
                    for p, style, name in includes]
        if any(child is not None and child not in deps for _,_,_,child in resolved):
            return None
        linked = {p for c in compats for p in self.bindings.get(c, [])}
        linked.update(p for c in compats for p in self.drivers.get(re.sub(r'[^A-Za-z0-9_]','_',c).lower(), ()))
        return digest([[(p, self.ids.get(p)) for p in sorted(deps)], resolved,
                       [(p, self.ids.get(p)) for p in sorted(linked)],
                       [(c, sorted(self.bindings.get(c, [])), sorted(self.drivers.get(re.sub(r'[^A-Za-z0-9_]','_',c).lower(), ()))) for c in sorted(compats)]])

    def target(self, folder, target, arch, metadata_path):
        # Exact target convention. Legacy same-stem YAML is allowed only if its
        # identifier was already matched by caller (not if a sibling exists).
        stem=target.replace('/','_')
        exact=folder+'/'+stem+'.dts'
        legacy=str(PurePosixPath(metadata_path).with_suffix('.dts'))
        entry=exact if exact in self.data else legacy if legacy in self.data else None
        if not entry: return {'entry':None,'nodes':[],'features':[],'present_features':[]}
        key = digest([folder,target,arch,metadata_path,entry])
        old = self.previous.get(key)
        if old and old['fingerprint'] == self.dependency_fingerprint(old['deps'], old['includes'], old['compats'], arch):
            self.results[key] = old
            self.hits += 1
            return old['result']
        self.misses += 1
        records=defaultdict(lambda:{'compatible':{},'status':{}})
        visited=set(); include_refs=[]
        def visit(p):
            if p in visited: return
            visited.add(p)
            includes, props=self.parsed(p)
            for style,name in includes:
                include_refs.append((p,style,name))
                child=self.resolve(p,style,name,arch)
                if child: visit(child)
            for label,values in props.items():
                for field in ('compatible','status'):
                    if field in values: records[label][field][p]=values[field]
        visit(entry)
        evidence=[]; features=set(); present=set(); all_compats=set()
        for label,rec in records.items():
            compats={v for vs in rec['compatible'].values() for v in vs}
            all_compats.update(compats)
            statuses={v for vs in rec['status'].values() for v in vs}
            # Use the last scanned literal (includes before including file).
            # Missing status defaults to okay in DTS, but this remains a hint
            # because this scanner does not evaluate conditions/parent status.
            last=next(reversed(rec['status'].values()),())
            positive=not statuses or bool(set(last) & {'okay','ok'})
            for compat in sorted(compats):
                bindings=self.bindings.get(compat,[])
                fs=set(SPECIAL.get(compat,()))
                for p in bindings:
                    family=p.split('/')[2]
                    if family in FAMILIES: fs.add(FAMILIES[family])
                if not fs: continue
                present.update(fs)
                if positive: features.update(fs)
                evidence.append({'node':label,'compatible':compat,'features':sorted(fs),
                    'status':'status omitted (default okay in DTS)' if not statuses else 'last scanned literal okay' if positive else 'last scanned literal not okay',
                    'status_values':sorted(statuses),'positive':positive,
                    'compatible_paths':sorted(p for p,vs in rec['compatible'].items() if compat in vs),
                    'status_paths':list(rec['status']), 'binding_paths':sorted(bindings),
                    'driver_paths':sorted({p for c in compats for p in self.drivers.get(re.sub(r'[^A-Za-z0-9_]','_',c).lower(),())})})
        fp=self.dependency_fingerprint(visited,include_refs,all_compats,arch)
        result={'entry':entry,'nodes':evidence,'features':sorted(features),'present_features':sorted(present),'input_fingerprint':fp}
        self.results[key]={'deps':sorted(visited),'includes':include_refs,'compats':sorted(all_compats),'fingerprint':fp,'result':result}
        return result
