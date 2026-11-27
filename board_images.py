"""Discover revision-pinned board photos and publish unchanged raster Git blobs.

No checkout, web requests, SVG execution, or guessed images from other boards.
"""
from collections import Counter, defaultdict
import hashlib
import logging
from pathlib import PurePosixPath
import re
import subprocess
from urllib.parse import quote
from html import escape

FORMATS = ('.webp', '.png', '.jpg', '.jpeg', '.gif')
MAX_BYTES = 4 * 1024 * 1024
GENERATED = re.compile(r'[0-9a-f]{40}(?:[0-9a-f]{24})?\.(?:webp|png|jpg|jpeg|gif)\Z')


def normal(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def select(boards, files):
    """Prefer upstream board-name matches; never assign an arbitrary shared image.

    files: {path: (Git blob ID, byte length)}. Accept named assets anywhere in
    the board folder, including its documentation directory.
    """
    counts = Counter(b['folder'] for b in boards.values())
    by_folder = defaultdict(list)
    folders = set(counts)
    for path, (oid, size) in files.items():
        p = PurePosixPath(path)
        if p.suffix.lower() not in FORMATS or not 0 < size <= MAX_BYTES:
            continue
        for parent in p.parents:
            folder = str(parent)
            if folder in folders:
                by_folder[folder].append((p, oid, size))
                break
    result = {}
    for key, b in boards.items():
        name = normal(b['name'])
        folder_name = normal(PurePosixPath(b['folder']).name)
        choices = []
        for p, oid, size in by_folder[b['folder']]:
            stem = normal(p.stem)
            if stem == name:
                rank = 0
            elif counts[b['folder']] == 1 and stem == folder_name:
                rank = 1
            elif counts[b['folder']] == 1 and any(stem == normal(prefix) for prefix in ('_'.join(b['name'].split('_')[:i]) for i in range(len(b['name'].split('_'))-1, 0, -1)) if len(normal(prefix)) >= 5):
                # Upstream also tries progressively shorter board-name prefixes.
                rank = 2
            elif counts[b['folder']] == 1 and len(name) >= 5 and name in stem and not any(word in stem for word in ('pinout','schematic','diagram','pinmap','pinmapping','dimensions','layout','blockdiagram')):
                # A board-specific photo suffix (e.g. _front or _top).
                rank = 3
            else:
                continue
            relative = p.relative_to(b['folder'])
            documented = relative.parts[0] in ('doc','docs')
            choices.append((rank, -len(stem) if rank == 2 else 0, 0 if documented else 1, len(p.parts), FORMATS.index(p.suffix.lower()), str(p), oid, size))
        if choices:
            _, _, _, _, _, path, oid, size = min(choices)
            result[key] = (path, oid, size)
    return result


def valid_raster(data, suffix):
    return {'webp': data[:4] == b'RIFF' and data[8:12] == b'WEBP',
            'png': data.startswith(b'\x89PNG\r\n\x1a\n'),
            'jpg': data.startswith(b'\xff\xd8\xff'), 'jpeg': data.startswith(b'\xff\xd8\xff'),
            'gif': data.startswith((b'GIF87a', b'GIF89a'))}.get(suffix, False)


def git_digest(data, oid):
    h = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
    h.update(f'blob {len(data)}\0'.encode()); h.update(data)
    return h.hexdigest()


def read_blobs(repo, ids):
    """Bound memory by batching a few already size-limited blobs at a time."""
    for start in range(0, len(ids), 16):
        group = ids[start:start+16]
        raw = subprocess.check_output(['git', '-C', str(repo.path), 'cat-file', '--batch'],
                                      input=('\n'.join(group)+'\n').encode())
        pos = 0
        for oid in group:
            end = raw.index(b'\n', pos); header = raw[pos:end].split(); pos = end+1
            if len(header) != 3 or header[:2] != [oid.encode(), b'blob']:
                raise RuntimeError(f'Cannot extract board image blob {oid}')
            n = int(header[2]); data = raw[pos:pos+n]; pos += n+1
            if len(data) != n or n > MAX_BYTES or git_digest(data, oid) != oid:
                raise RuntimeError(f'Invalid board image blob {oid}')
            yield oid, data


def publish(repo, head, boards, docs, enabled=True):
    """Return board -> image metadata; reuse files by immutable Git blob ID."""
    if not isinstance(enabled, bool):
        raise ValueError('board_images must be true or false')
    directory = docs/'data'/'board-images'
    directory.mkdir(parents=True, exist_ok=True)
    selected = {}
    if enabled and boards:
        files = {}
        for record in repo.git('ls-tree', '-r', '-l', '-z', head, '--', 'boards').split('\0'):
            if not record: continue
            meta, path = record.split('\t', 1)
            mode, kind, oid, size = meta.split()
            if kind == 'blob' and mode in ('100644', '100755') and PurePosixPath(path).suffix.lower() in FORMATS:
                files[path] = (oid, int(size))
        selected = select(boards, files)
    desired = defaultdict(list)
    for key, (path, oid, size) in selected.items():
        name = oid + PurePosixPath(path).suffix.lower()
        desired[name].append((key, path, oid, size))
    valid = set(); missing = defaultdict(list)
    for name, group in desired.items():
        oid = group[0][2]; target = directory/name
        if target.is_file() and target.stat().st_size == group[0][3]:
            data = target.read_bytes()
            if git_digest(data, oid) == oid and valid_raster(data, target.suffix[1:]):
                valid.add(name); continue
        missing[oid].append(name)
    changed = 0
    for oid, data in read_blobs(repo, sorted(missing)):
        for name in missing[oid]:
            target = directory/name
            if not valid_raster(data, target.suffix[1:]):
                logging.warning('Skipping non-raster board image: %s', desired[name][0][1]); continue
            if not target.is_file() or target.read_bytes() != data:
                target.write_bytes(data); changed += 1
            valid.add(name)
    result = {}
    for name in sorted(valid):
        for key, path, oid, size in desired[name]:
            result[key] = {'url':'data/board-images/'+name, 'path':path}
    # Only remove files we own. Keep the prior published generation for cached HTML.
    previous = set()
    catalog = docs/'intelligence.json'
    if catalog.is_file() and enabled:
        import json
        try:
            previous = {b.get('image_url','').rsplit('/',1)[-1] for b in json.loads(catalog.read_bytes()).get('boards', [])}
        except (ValueError, TypeError, AttributeError):
            logging.warning('Cannot read previous image references; retaining only current images')
    for path in directory.iterdir():
        if path.is_file() and GENERATED.fullmatch(path.name) and path.name not in valid and path.name not in previous:
            path.unlink()
    total = sum((directory/n).stat().st_size for n in valid)
    logging.info('Board images: %d/%d boards, %d unique files, %d changed/new, %.2f MiB current',len(result),len(boards),len(valid),changed,total/1048576)
    return result


def overview(b, image, revision, upstream):
    """Compact static card; image is independent of evidence tables and JS."""
    def url(path): return f'{upstream}/blob/{revision}/{quote(path,safe="/")}'
    def a(href, text): return f'<a href="{escape(href, quote=True)}">{escape(text)}</a>'
    name = escape(b['full_name'])
    lines = ['<section class="pulse-board-overview" aria-label="Board overview">',
             '<div class="pulse-board-photo">']
    if image:
        local = '../'+image['url']
        lines += [f'<a href="{local}"><img src="{local}" alt="{name}" loading="lazy" decoding="async"></a>',
                  '<small>Upstream Zephyr documentation · '+a(url(image['path']), 'Image source')+'</small>']
    else:
        lines += ['<div class="pulse-board-no-photo"><span class="pulse-icon pulse-i-board" aria-hidden="true"></span><span>No upstream board image available</span></div>']
    lines += ['</div>', '<div class="pulse-board-overview-meta">', '<strong>Board overview</strong>', '<dl>',
              f'<dt>Board</dt><dd><code>{escape(b["name"])}</code></dd>',
              f'<dt>Vendor</dt><dd>{a("../vendors.html?vendor="+quote(b["vendor"],safe=""),b["vendor_name"])}</dd>',
              '<dt>SoCs</dt><dd>'+(', '.join(a('../boards.html?subject='+quote(s,safe=''),s) for s in b['socs']) or 'Not declared')+'</dd>',
              '<dt>Architecture</dt><dd>'+escape(', '.join(sorted({m['arch'] for m in b.get('metadata',{}).values() if m.get('arch')})) or 'Not declared')+'</dd>',
              '</dl>', '<div class="pulse-board-overview-links">'+a(f'{upstream}/tree/{revision}/{quote(b["folder"],safe="/")}', 'Board source')+' · '+a(url(b['source']), 'Board definition')+'</div>']
    if b.get('doc_source'):
        lines += ['<div class="pulse-board-overview-links">'+a('https://docs.zephyrproject.org/latest/'+quote(b['doc_source'][:-4],safe='/')+'.html','Official board documentation (latest)')+' · '+a(url(b['doc_source']),'Documentation source')+'</div>']
    return '\n'.join(lines+['</div>', '</section>'])
