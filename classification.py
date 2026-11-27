"""Conservative subsystem classification, separate from hardware-support evidence."""
from pathlib import PurePosixPath
import re

# Increment only when classification semantics change, not on unrelated releases.
VERSION = '3'


def path_category(path):
    p = PurePosixPath(path)
    if path in ('west.yml', 'west.yaml') or (path.startswith('submanifests/') and p.suffix in ('.yml', '.yaml')):
        return 'manifest', 'Manifest change'
    if path.startswith(('dts/bindings/', 'include/zephyr/dt-bindings/')):
        return 'dt_bindings', 'Binding change'
    if path.startswith('samples/'):
        return 'samples', 'Sample change'
    if path.startswith('tests/'):
        return 'tests', 'Test change'
    if path.startswith('subsys/'):
        return 'subsys', 'Subsystem change'
    if path.startswith(('kernel/', 'arch/', 'include/zephyr/kernel/', 'include/zephyr/arch/')) or path == 'include/zephyr/kernel.h':
        return 'kernel', 'Kernel / architecture change'
    if path.startswith(('doc/', 'docs/')) or '/doc/' in path or '/docs/' in path or p.suffix in ('.rst', '.md'):
        return 'docs', 'Documentation'
    if path == 'include/zephyr/devicetree.h' or path.startswith('include/zephyr/devicetree/'):
        return 'dts', 'API change'
    if path.startswith(('scripts/dts/', 'cmake/modules/dts')):
        return 'dts', 'Tooling change'
    if p.suffix in ('.dts', '.dtsi', '.overlay'):
        return 'dts', 'Configuration change'
    if path.startswith('dts/'):
        return 'dts', 'Configuration change'
    if path.startswith(('drivers/sensor/', 'include/zephyr/drivers/sensor/')) or path == 'include/zephyr/drivers/sensor.h':
        return 'sensor', 'Sensor change'
    if path.startswith(('drivers/', 'include/zephyr/drivers/')):
        return 'driver', 'Driver change'
    if path.startswith(('soc/', 'include/zephyr/soc/')):
        return 'soc', 'SoC change'
    if path.startswith('boards/'):
        return 'board_change', 'Board maintenance'
    return None


def prefix_category(subject):
    match = re.match(r'^\s*(dt[-_]bindings|dts|devicetree|drivers?|sensors?|soc|boards?|docs?|documentation|samples?|tests?|subsys|kernel|arch)\s*:', subject, re.I)
    if not match:
        return None
    key = match.group(1).lower()
    return {'dts':'dts', 'devicetree':'dts', 'driver':'driver', 'drivers':'driver', 'sensor':'sensor', 'sensors':'sensor', 'soc':'soc', 'board':'board_change', 'boards':'board_change', 'doc':'docs', 'docs':'docs', 'documentation':'docs','dt-bindings':'dt_bindings','dt_bindings':'dt_bindings','sample':'samples','samples':'samples','test':'tests','tests':'tests','subsys':'subsys','kernel':'kernel','arch':'kernel'}[key]


def api_doc_only(repo, sha, parent, path):
    # Deliberately narrow: only changed Doxygen directive lines, not arbitrary
    # lines beginning with '*' (which can also be C expressions).
    if not parent:
        return False
    diff = repo.git('diff', '--no-ext-diff', '--unified=0', parent, sha, '--', path)
    in_hunk = False; lines = []
    for line in diff.splitlines():
        if line.startswith('@@'): in_hunk = True; continue
        if in_hunk and line.startswith(('+','-')): lines.append(line[1:])
    return bool(lines) and all(re.match(r'^\s*\*\s+[@\\][A-Za-z]+\b', line) for line in lines)


def path_subject(kind, path, headline):
    p = PurePosixPath(path)
    if kind == 'dts' and path.startswith('include/zephyr/devicetree'):
        macros = re.findall(r'\bDT_[A-Z][A-Z0-9_]*\b', headline)
        if len(set(macros)) == 1: return macros[0]
    if kind == 'board_change' and len(p.parts) >= 4 and p.parts[1] not in ('common','shields','extensions'):
        return p.parts[2]
    if kind == 'dt_bindings' and path.startswith('dts/bindings/') and ',' in p.stem:
        return p.stem
    return p.name


def supplement(repo, sha, parent, changes, headline, semantic):
    """Keep precise semantic events, then add bounded, path-backed summaries.

    At most one generic event per subsystem/change type/subject; do not emit
    generic duplicates for paths already represented by a semantic event.
    Other is one event per commit; the commit link exposes the complete diff.
    """
    events = set(semantic)
    covered_paths = {e[4] for e in events}
    # New-board metadata is stronger than routine maintenance in that folder.
    from pulse import board_folder
    new_folders = {board_folder(e[4]) for e in events if e[0] == 'board'} - {None}
    groups = {}
    for status, old, new in changes:
        path = new or old
        if not path or path in covered_paths: continue
        result = path_category(path)
        if not result: continue
        kind, typ = result
        if kind == 'board_change' and board_folder(path) in new_folders: continue
        if typ == 'API change' and status == 'M' and api_doc_only(repo,sha,parent,path): typ = 'API documentation'
        elif status == 'D': typ = 'Source removal'
        elif status in ('R','C'): typ = 'Source relocation' if status == 'R' else 'Source copy'
        elif typ == 'Binding change' and status == 'A': typ = 'New binding file'
        elif typ not in ('Documentation','API change','Tooling change','Test change','Binding change','New binding file') and re.search(r'\b(fix|fixes|fixed|bugfix|regression)\b',headline,re.I): typ = 'Fix (headline signal)'
        subject = path_subject(kind,path,headline)
        groups.setdefault((kind,typ,subject), []).append((path,status))
    for (kind,typ,subject), paths in sorted(groups.items()):
        path,status = sorted(paths, key=lambda x:(x[1]=='D',x[0]))[0]
        detail = f'{typ}: source path identifies affected subsystem. No new hardware capability inferred.'
        if typ == 'API documentation': detail = 'API documentation: changed lines are Doxygen directives; no implementation change detected.'
        if len(paths)>1: detail += f' {len(paths)} related changed files; inspect commit for complete diff.'
        events.add((kind,subject,detail,'observed',path))
    if not events:
        paths = sorted(((new or old,status) for status,old,new in changes if new or old),key=lambda x:(x[1]=='D',x[0]))
        path = paths[0][0] if paths else ''
        kind = prefix_category(headline)
        if kind:
            events.add((kind,headline,'Headline classification: recognized subsystem prefix; source path did not establish the category. No new hardware capability inferred.','candidate',path))
        else:
            detail = 'Unclassified: no subsystem or priority rule matched. Inspect commit for details.'
            if len(paths)>1: detail += f' {len(paths)} changed files; source link is representative.'
            events.add(('other',headline,detail,'unclassified',path))
    return sorted(events)


def change_type(detail):
    """Stable display taxonomy for existing semantic evidence and new summaries."""
    if detail.startswith('New board name'): return 'New board'
    if detail.startswith('New SoC or variant'): return 'New variant'
    if detail.startswith('New supported metadata'): return 'Capability declaration'
    if detail.startswith('New target metadata'): return 'Target metadata'
    if detail.startswith('New enabled Kconfig'): return 'Kconfig change'
    if 'disabled → okay' in detail or 'explicit status okay added' in detail: return 'Peripheral enablement'
    if 'compatible changed to' in detail: return 'Compatible change'
    if detail.startswith('New devicetree source'): return 'New DTS source'
    if detail.startswith('Devicetree source modified'): return 'Configuration change'
    if detail.startswith('New or changed devicetree binding'): return 'Binding compatible'
    if detail.startswith('Sensor binding introduced'): return 'Sensor binding'
    if detail.startswith('New DT_DRV_COMPAT'): return 'Driver compatible'
    if detail.startswith('New implementation file'): return 'New implementation file'
    if detail.startswith('New SoC name'): return 'New SoC'
    if detail.startswith(('New SoC metadata','SoC metadata changed')): return 'SoC metadata'
    if detail.startswith('New documentation source'): return 'Documentation'
    if detail.startswith('New driver'): return 'Possible driver support'
    return detail.split(':',1)[0] if ':' in detail else 'Unclassified'
