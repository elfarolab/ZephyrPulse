"""Disposable SQLite caches and deterministic content fingerprints.

Cache entries are versioned independently by their analysis dependencies. Nothing here is
needed to recover the news database; deleting the cache only costs computation.
"""
import ast
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


# Independent cache producers. The Git methods are explicit roots because repo
# is passed as an object, so static name analysis cannot resolve its methods.
# Add roots for any other indirect/dynamic producer dependencies introduced later.
CACHE_FORMAT = 2
_GIT_READ = (('pulse', 'Git.__init__'), ('pulse', 'Git.git'))
_CACHE_ROOTS = {
    'inventory': (*_GIT_READ, ('intelligence', 'inventory')),
    'release-snapshot': (*_GIT_READ, ('comparison', 'release_snapshots')),
    'recent-commit-files': (*_GIT_READ, ('pulse', 'Git.parent'),
                            ('pulse', 'Git.changes'), ('news_groups', 'recent_files')),
}
# The old global source fingerprint of the exact v0.3.30 release. Only that
# baseline is eligible for promotion, and only while a producer's scoped
# fingerprint still matches its migration baseline below.
_LEGACY_VERSION = '9b2f5f105a579b1f9c8c0e08db9814dcbcec25fddb8179a37c8f5490e5d58c36'
_LEGACY_BASELINE = {
    'inventory': '06582b02fa3268d8eed7746c0df75c2c8d19fee3c9faca739a72531ecfe49f1a',
    'release-snapshot': 'eb0df94b701f481626a141d18f5ee3250c768636b8c82840531c0220869ebbfe',
    'recent-commit-files': '745381955ae49a7c0d6dd08e5b894ec70b6368d6d5a07705661bc13cec5e7afb',
}


class _Sources:
    """Follow local functions, constants, classes and direct imports by source.

    Hash selected source spans, not entire mixed-purpose modules. A newly
    referenced local helper is followed automatically. Cache I/O and progress
    reporting are infrastructure rather than analysis dependencies; changes to
    cache encoding/validation require a CACHE_FORMAT bump. No upstream source
    or application module is executed to calculate these fingerprints.
    """
    def __init__(self, root):
        self.root = root
        self.modules = {}
        self.parts = {}

    def path(self, module):
        return self.root.joinpath(*module.split('.')).with_suffix('.py')

    def module(self, module):
        if module not in self.modules:
            source = self.path(module).read_text(encoding='utf-8')
            symbols = {}
            for node in ast.parse(source).body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols[node.name] = node
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name): symbols[target.id] = node
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        symbols[alias.asname or alias.name.split('.')[0]] = node
            self.modules[module] = source.splitlines(keepends=True), symbols
        return self.modules[module]

    def imports(self, node):
        if isinstance(node, ast.ImportFrom) and not node.level and node.module:
            if node.module == 'progress' or not self.path(node.module).is_file(): return
            for alias in node.names:
                if node.module == 'performance' and alias.name in ('load', 'save'): continue
                if alias.name == '*':
                    self.whole(node.module)
                else:
                    self.visit(node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != 'progress' and self.path(alias.name).is_file():
                    self.whole(alias.name)

    def whole(self, module):
        # A module-object import has no statically known attribute set. Hash
        # the full module and follow its imports conservatively.
        key = (module, '*')
        if key in self.parts: return
        source = self.path(module).read_text(encoding='utf-8')
        self.parts[key] = source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Import, ast.ImportFrom)): self.imports(node)

    def visit(self, module, symbol):
        key = (module, symbol)
        if key in self.parts: return
        lines, symbols = self.module(module)
        names = symbol.split('.')
        node = symbols[names[0]]
        for name in names[1:]:
            node = next(child for child in node.body if getattr(child, 'name', None) == name)
        start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        self.parts[key] = ''.join(lines[start-1:node.end_lineno])
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)): self.imports(child)
            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in symbols:
                # Local names may shadow a global; including the latter is safe.
                self.visit(module, child.id)


def _fingerprints(root):
    versions = {}
    for scope, roots_ in _CACHE_ROOTS.items():
        graph = _Sources(root)
        for module, symbol in roots_: graph.visit(module, symbol)
        versions[scope] = digest([CACHE_FORMAT, scope, sorted(graph.parts.items())])
    return versions


@lru_cache(maxsize=1)
def _versions():
    return _fingerprints(Path(__file__).resolve().parent)


def cache_scope(key):
    if key == 'inventory': return 'inventory'
    if key.startswith('release-snapshot:'): return 'release-snapshot'
    if key.startswith('recent-commit-files:'): return 'recent-commit-files'
    raise ValueError(f'Unregistered performance cache key: {key}')


def analysis_version(key):
    return _versions()[cache_scope(key)]


def _ensure_table(db):
    db.execute('CREATE TABLE IF NOT EXISTS performance_cache (key TEXT PRIMARY KEY, version TEXT NOT NULL, payload TEXT NOT NULL)')


def load(db, key):
    if db is None: return None
    _ensure_table(db)
    scope = cache_scope(key)
    version = analysis_version(key)
    row = db.execute('SELECT version,payload FROM performance_cache WHERE key=?', (key,)).fetchone()
    if not row: return None
    old, payload = row
    promote = old == _LEGACY_VERSION and version == _LEGACY_BASELINE.get(scope)
    if old != version and not promote:
        logging.info('Performance cache: %s fingerprint changed; recomputing', key)
        return None
    try: result = json.loads(payload)
    except (ValueError, TypeError):
        logging.warning('Ignoring invalid performance cache: %s', key)
        return None
    if promote:
        db.execute('UPDATE performance_cache SET version=? WHERE key=? AND version=?', (version, key, old))
        db.commit()
        logging.info('Performance cache: %s migrated to scoped fingerprint; existing data retained', key)
    return result


def save(db, key, value):
    if db is None: return
    _ensure_table(db)
    db.execute('INSERT OR REPLACE INTO performance_cache VALUES(?,?,?)', (key, analysis_version(key), json.dumps(value, ensure_ascii=False)))
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
