import json
from unittest import TestCase
from unittest.mock import patch
from generators import get_generator, build_site
from test_generators import Fake, ROOT
import test_generators


class DisabledSearchIndexTests(TestCase):
    setUp = test_generators.GeneratorTests.setUp

    def prepare(self):
        (self.root/'zensical.toml').write_bytes((ROOT/'zensical.toml').read_bytes())

    def fake_run(self, workspace, text, clean, data):
        import shutil
        if (workspace/'site').exists():
            shutil.rmtree(workspace/'site')
        Fake().render(self.root, workspace, 'https://example.invalid/')
        if data is not None:
            (workspace/'site/search.json').write_text(data)

    def test_empty_index_incremental_reuses_cache(self):
        self.prepare()
        g = get_generator({'incremental': True, 'native_search': False})
        calls = []
        def run(work, text, clean):
            calls.append(clean)
            self.fake_run(work, text, clean, json.dumps({'config': {'lang':['en']}, 'items': []}))
        with patch.object(g, '_run', side_effect=run):
            for _ in range(2):
                out = build_site(self.root, g, 'https://example.invalid/')
                self.assertEqual(json.loads((out/'search.json').read_text())['items'], [])
                self.assertTrue((self.root/'.pulse-render-cache/signature').exists())
        self.assertEqual(calls, [True])

    def test_nonempty_cached_index_triggers_clean_fallback(self):
        self.prepare()
        g = get_generator({'incremental': True, 'native_search': False})
        def run(work, text, clean):
            items = [{'title': 'stale'}] if work.name == '.pulse-render-cache' else []
            self.fake_run(work, text, clean, json.dumps({'items': items}))
        with patch.object(g, '_run', side_effect=run) as mocked, self.assertLogs(level='ERROR') as logs:
            out = build_site(self.root, g, 'https://example.invalid/')
        self.assertIn('retrying a clean staged build', logs.output[0])
        self.assertEqual(mocked.call_count, 2)
        self.assertFalse((self.root/'.pulse-render-cache').exists())
        self.assertEqual(json.loads((out/'search.json').read_text())['items'], [])

    def test_bad_clean_index_preserves_previous_site(self):
        self.prepare()
        g = get_generator({'native_search': False})
        for data in ('{bad', '{}', '[]', '{"items":null}', '{"items":[{"title":"stale"}]}'):
            with self.subTest(data=data), patch.object(g, '_run', side_effect=lambda w,t,clean: self.fake_run(w,t,clean,data)):
                with self.assertRaises(RuntimeError):
                    build_site(self.root, g, 'https://example.invalid/')
                self.assertTrue((self.root/'site/obsolete.html').exists())

    def test_missing_index_and_native_enabled(self):
        self.prepare()
        for native,data in [(False,None),(True,'{"items":[{"title":"valid"}]}')]:
            g = get_generator({'native_search':native})
            with patch.object(g, '_run', side_effect=lambda w,t,clean: self.fake_run(w,t,clean,data)):
                out = build_site(self.root,g,'https://example.invalid/')
            self.assertEqual((out/'search.json').exists(), native)
