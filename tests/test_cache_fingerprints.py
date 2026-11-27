"""Check isolation, shared dependencies and safe migration of exact v0.3.30 caches."""
from pathlib import Path
import shutil
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch
import performance as cache

ROOT = Path(cache.__file__).resolve().parent
KEYS = ('inventory', 'release-snapshot:v4.5.0', 'recent-commit-files:v1')


class CacheFingerprintTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for p in ROOT.glob('*.py'):
            shutil.copyfile(p, self.root/p.name)
        self.base = cache._fingerprints(self.root)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)

    def modified(self, file, before, after):
        p = self.root/file
        source = p.read_text()
        self.assertIn(before, source)
        p.write_text(source.replace(before, after, 1))
        try:
            return cache._fingerprints(self.root)
        finally:
            p.write_text(source)

    def changes(self, file, before, after):
        new = self.modified(file, before, after)
        return {k for k in new if new[k] != self.base[k]}

    def test_presentation_and_classifier_do_not_invalidate(self):
        self.assertEqual(self.changes('pulse.py', 'def render(db,', 'def render_renamed(db,'), set())
        self.assertEqual(self.changes('intelligence.py', 'def render_extra(', 'def render_extra_changed('), set())
        self.assertEqual(self.changes('pulse.py', 'def classify(', 'def classify_changed('), set())
        self.assertEqual(self.changes('comparison.py', 'def comparison_data(', 'def comparison_data_changed('), set())
        self.assertEqual(self.changes('news_groups.py', 'def manifest_files(', 'def manifest_files_changed('), set())

    def test_independent_and_shared_dependencies(self):
        self.assertEqual(self.changes('intelligence.py', "'nxp_semiconductors':'nxp'", "'nxp_semiconductors':'changed'"), {'inventory'})
        self.assertEqual(self.changes('comparison.py', "'canfd':'can-fd'", "'canfd':'can'"), {'release-snapshot'})
        self.assertEqual(self.changes('pulse.py', "'-z', '-M', parent", "'-z', '-M90%', parent"), {'recent-commit-files'})
        self.assertEqual(self.changes('hardware_evidence.py', "'nxp,els': ('crypto',)", "'nxp,els': ('rng',)"), {'inventory','release-snapshot'})
        self.assertEqual(self.changes('pulse.py', 'result = yaml.safe_load(s)', 'result = yaml.safe_load(s.strip())'), {'inventory','release-snapshot'})
        self.assertEqual(self.changes('pulse.py', 'args, cwd=cwd, stdout=', 'args, cwd=cwd, timeout=60, stdout='), set(self.base))

    def test_new_direct_helper_is_followed(self):
        p = self.root/'intelligence.py'
        s = p.read_text().replace('return boards,evidence_index.results', 'return identity(boards),evidence_index.results')
        p.write_text(s+'\n\ndef identity(value):\n    return value\n')
        before = cache._fingerprints(self.root)
        p.write_text(s+'\n\ndef identity(value):\n    return dict(value)\n')
        after = cache._fingerprints(self.root)
        self.assertEqual({k for k in after if after[k]!=before[k]}, {'inventory'})

    def test_cache_load_only_invalidates_affected_scope(self):
        for key in KEYS: cache.save(self.db, key, {'key':key})
        new = self.modified('comparison.py', "'canfd':'can-fd'", "'canfd':'can'")
        with patch.object(cache, '_versions', return_value=new), self.assertLogs(level='INFO'):
            self.assertEqual(cache.load(self.db, KEYS[0]), {'key':KEYS[0]})
            self.assertIsNone(cache.load(self.db, KEYS[1]))
            self.assertEqual(cache.load(self.db, KEYS[2]), {'key':KEYS[2]})

    def test_exact_legacy_baseline_promotes_without_payload_change(self):
        if (ROOT/'VERSION').read_text().strip() == '0.3.31':
            self.assertEqual(cache._LEGACY_BASELINE, self.base)
        for key in KEYS:
            cache.save(self.db,key,{'key':key})
        self.db.execute('UPDATE performance_cache SET version=?',(cache._LEGACY_VERSION,))
        self.db.commit()
        payloads = dict(self.db.execute('SELECT key,payload FROM performance_cache'))
        with patch.object(cache, '_versions', return_value=cache._LEGACY_BASELINE), self.assertLogs(level='INFO') as logs:
            for key in KEYS: self.assertEqual(cache.load(self.db,key),{'key':key})
        self.assertEqual(sum('migrated to scoped fingerprint' in x for x in logs.output),3)
        self.assertEqual(dict(self.db.execute('SELECT key,payload FROM performance_cache')),payloads)
        for key, version in self.db.execute('SELECT key,version FROM performance_cache'):
            self.assertEqual(version,cache._LEGACY_BASELINE[cache.cache_scope(key)])

    def test_old_or_modified_legacy_cache_not_promoted(self):
        for key in KEYS: cache.save(self.db,key,{'key':key})
        self.db.execute('UPDATE performance_cache SET version=?',(cache._LEGACY_VERSION,))
        self.db.execute('UPDATE performance_cache SET version=? WHERE key=?',('unrecognized-old-source',KEYS[2]))
        self.db.commit()
        new = {**cache._LEGACY_BASELINE, 'release-snapshot': 'changed-producer'}
        with patch.object(cache,'_versions',return_value=new), self.assertLogs(level='INFO'):
            self.assertEqual(cache.load(self.db,KEYS[0]),{'key':KEYS[0]})
            self.assertIsNone(cache.load(self.db,KEYS[1]))
            self.assertIsNone(cache.load(self.db,KEYS[2]))

    def test_invalid_payload_not_promoted(self):
        cache.save(self.db,KEYS[0],{})
        self.db.execute('UPDATE performance_cache SET version=?,payload=?',(cache._LEGACY_VERSION,'invalid json'))
        with patch.object(cache, '_versions', return_value=cache._LEGACY_BASELINE), self.assertLogs(level='WARNING'):
            self.assertIsNone(cache.load(self.db,KEYS[0]))
        self.assertEqual(self.db.execute('SELECT version FROM performance_cache').fetchone()[0],cache._LEGACY_VERSION)
