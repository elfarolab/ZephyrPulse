"""Version local application CSS/JS references without modifying static assets.

Run on the staged output, not on Zensical's persistent renderer cache. The
same content produces the same URL on every page, including nested profiles.
"""
import hashlib
import logging
import posixpath
import re
from urllib.parse import urlsplit, urlunsplit, unquote

# Only rewrite the renderer's script and stylesheet tags, not ordinary links.
TAG = re.compile(r'<(?:script|link)\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*>', re.I)
ATTR = re.compile(r'''(?P<lead>\s(?:src|href)\s*=\s*)(?P<q>["'])(?P<url>.*?)(?P=q)''', re.I)


def version_assets(output):
    assets = output/'assets'
    if not assets.is_dir(): return 0
    versions = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                for p in assets.iterdir() if p.is_file() and p.suffix in ('.js', '.css')}
    if not versions: return 0
    changed = 0
    for page in output.rglob('*.html'):
        rel = page.relative_to(output).as_posix()
        def tag(match):
            def attr(m):
                raw = m['url']
                u = urlsplit(raw)
                if u.scheme or u.netloc: return m[0]
                path = unquote(u.path)
                key = posixpath.normpath(path.lstrip('/') if path.startswith('/') else posixpath.join(posixpath.dirname(rel),path))
                if key not in versions: return m[0]
                # Preserve other parameters and replace an existing fingerprint.
                parts = [p for p in re.split(r'&amp;|&',u.query) if p and not p.startswith('pulse_v=')]
                parts.append('pulse_v='+versions[key])
                url = urlunsplit(('', '', u.path, '&amp;'.join(parts), u.fragment))
                return m['lead']+m['q']+url+m['q']
            return ATTR.sub(attr,match[0])
        original = page.read_bytes().decode('utf-8')
        result = TAG.sub(tag, original)
        if result != original:
            page.write_bytes(result.encode('utf-8')); changed += 1
    logging.info('Asset versioning: %d CSS/JS assets; %d HTML pages fingerprinted',len(versions),changed)
    return changed
