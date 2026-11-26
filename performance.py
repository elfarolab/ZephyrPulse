"""Disposable SQLite caches and deterministic content fingerprints.

Cache entries are versioned by the actual analysis source. Nothing here is
needed to recover the news database; deleting the cache only costs computation.
"""
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=1)
def analysis_version():
    root = Path(__file__).resolve().parent
    return digest([(name, hashlib.sha256((root/name).read_bytes()).hexdigest())
                   for name in ('performance.py', 'intelligence.py', 'hardware_evidence.py', 'comparison.py', 'pulse.py')])


def load(db, key):
    if db is None: return None
    db.execute('CREATE TABLE IF NOT EXISTS performance_cache (key TEXT PRIMARY KEY, version TEXT NOT NULL, payload TEXT NOT NULL)')
    row = db.execute('SELECT payload FROM performance_cache WHERE key=? AND version=?', (key, analysis_version())).fetchone()
    if row:
        try: return json.loads(row[0])
        except (ValueError, TypeError): logging.warning('Ignoring invalid performance cache: %s', key)
    return None


def save(db, key, value):
    if db is None: return
    db.execute('INSERT OR REPLACE INTO performance_cache VALUES(?,?,?)', (key, analysis_version(), json.dumps(value, ensure_ascii=False)))
    db.commit()


def trees(repo, ref, paths):
    """Git tree/blob IDs, including absent paths by omission; no timestamps."""
    out = repo.git('ls-tree', '-r', '-t', '-z', ref, '--', *paths)
    return {path: meta.split()[2] for record in out.split('\0') if record
            for meta, path in [record.split('\t', 1)]}


def roots(repo, ref, paths):
    out = repo.git('ls-tree', '-z', ref, '--', *paths)
    return {path: meta.split()[2] for record in out.split('\0') if record
            for meta, path in [record.split('\t', 1)]}
