"""Presentation-only grouping of category events. Keep raw event records untouched."""
import re
from collections import defaultdict

GROUPED = {'driver', 'sensor', 'docs', 'other', 'dts', 'soc', 'board_change'}
DRIVERS = {'driver', 'sensor'}
GENERIC = {'main', 'common', 'core', 'init', 'utils', 'util', 'test', 'tests', 'driver', 'drivers', 'config', 'cmakelists', 'kconfig', 'makefile', 'readme', 'sample', 'shell', 'api', 'types', 'module', 'binding', 'bindings', 'build', 'index'}


def unique(values):
    return list(dict.fromkeys(v for v in values if v))


def driver_identity(rows):
    subsystems, names = [], []
    for r in rows:
        path = r.get('path') or ''
        parts = path.split('/')
        if len(parts) < 3 or parts[0] != 'drivers':
            continue
        sub = parts[1]
        subsystems.append(sub)
        stem = parts[-1].rsplit('.', 1)[0].lower()
        if parts[-1].startswith('Kconfig.'):
            stem = parts[-1][8:].lower()
        elif parts[-1].lower().startswith(('kconfig', 'cmakelists', 'readme')):
            stem = ''
        elif len(parts) > 3:
            # Nested source directories normally identify the driver; for sensors
            # the first directory can be a vendor, followed by a driver directory.
            if sub == 'sensor' and len(parts) > 4:
                stem = parts[3].lower()
            elif sub != 'sensor':
                stem = parts[2].lower()
        if stem.startswith(sub + '_'):
            stem = stem[len(sub)+1:]
        if stem.endswith('_'+sub):
            stem = stem[:-(len(sub)+1)]
        if stem == sub:
            stem = ''
        if stem and stem not in GENERIC and re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', stem):
            names.append(stem)
    title = rows[0].get('commit_subject') or ''
    prefix = re.match(r'^drivers?\s*:\s*([\w-]+)\s*:', title, re.I)
    if not subsystems and prefix:
        subsystems.append(prefix[1].lower())
    if not subsystems and rows[0]['kind'] == 'sensor':
        subsystems.append('sensor')
    return ', '.join(unique(subsystems)) or 'Not identified', ', '.join(unique(names)) or 'Subsystem-level / not identified'


def group_scope(r, category):
    """Never merge unrelated named hardware just because the SHA matches."""
    path = r.get('path') or ''
    parts = path.split('/')
    subject = r['subject']
    if category == 'board_change':
        folder = '/'.join(parts[:3]) if len(parts) >= 4 and parts[0] == 'boards' else ''
        return (folder, subject), subject
    if category == 'soc':
        # Preserve named semantic SoC events; generic source filenames instead
        # group by their upstream vendor/family directory, not the basename.
        if len(parts) >= 3 and parts[0] == 'soc':
            folder = '/'.join(parts[:3] if len(parts) >= 4 else parts[:2])
            if subject == parts[-1] or subject == '/'.join(parts[:-1]):
                return (folder, ''), folder
            return (folder, subject), subject
        return (path, subject), subject
    return (), ''


def group_events(items, category):
    groups = defaultdict(list)
    for item in items:
        r = dict(item)
        # Do not merge unrelated boards/SoCs introduced by the same commit.
        scope, _ = group_scope(r, category)
        groups[(r['sha'], scope)].append(r)
    result = []
    for (sha, scope), rows in groups.items():
        subjects = unique(r['subject'] for r in rows)
        files = defaultdict(list)
        for r in rows:
            if r.get('path'):
                files[(r['path'], r.get('source_revision') or sha)].append(r)
        subs, driver = driver_identity(rows) if category in DRIVERS else ('', '')
        result.append(dict(rows=rows, sha=sha, subjects=subjects, files=files,
                           subsystem=subs, driver=driver, subject=group_scope(rows[0], category)[1] or ', '.join(subjects),
                           types=unique(r.get('change_type') or 'Unknown' for r in rows)))
    return result


def recent_files(db, repo):
    """Cache exact first-parent diff manifests for grouped commits in the recent window."""
    import logging
    from performance import load, save
    key = 'recent-commit-files:v1'
    old = load(db, key) or {}
    result = {}
    for sha, in db.execute('SELECT DISTINCT sha FROM events WHERE kind IN ('+','.join('?' for _ in GROUPED)+') ORDER BY sha', tuple(sorted(GROUPED))):
        if sha in old:
            result[sha] = old[sha]
            continue
        try:
            parent = repo.parent(sha)
            result[sha] = [dict(path=new or previous, revision=sha if new else parent or sha,
                                status=status, old_path=previous if status in ('R','C') else None)
                           for status, previous, new in repo.changes(sha, parent)]
        except RuntimeError as error:
            logging.warning('Commit file manifest unavailable for %s: %s', sha[:12], error)
    if result != old:
        save(db, key, result)
    logging.info('Recent commit file manifests: %d available, %d cache hits', len(result), len(result.keys() & old.keys()))
    return result


def manifest_files(group, manifest):
    """Show exact diff files, then any additional evidence paths separately."""
    evidence = group['files']
    if manifest is None:
        return [(p, rev, '', None, rows) for (p,rev),rows in evidence.items()], []
    files = [(f['path'], f['revision'], f['status'], f.get('old_path'), evidence.get((f['path'], f['revision']), [])) for f in manifest]
    keys = {(p,rev) for p,rev,*_ in files}
    extra = [(p,rev,'',None,rows) for (p,rev),rows in evidence.items() if (p,rev) not in keys]
    return files, extra
