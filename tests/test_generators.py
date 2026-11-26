import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tomllib
from generators import get_generator, build_site

ROOT=Path(__file__).resolve().parents[1]
MOUNTS={'compare':'pulse-comparator','settings':'pulse-settings','hardware-search':'pulse-hardware-search'}

class Fake:
    def __init__(self, fail=False, incomplete=False):self.fail=fail;self.incomplete=incomplete
    def render(self, project, workspace, site_url):
        output=workspace/'site';output.mkdir()
        for p in (workspace/'docs').rglob('*'):
            if not p.is_file():continue
            rel=p.relative_to(workspace/'docs');target=output/rel
            if p.suffix=='.md':target=target.with_suffix('.html')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
        if self.fail:raise RuntimeError('failed renderer')
        if self.incomplete:(output/'feed.xml').unlink()

class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);d=self.root/'docs';d.mkdir()
        for n in ('index','boards',*MOUNTS): (d/(n+'.md')).write_text(f'<div id="{MOUNTS.get(n,n)}"></div>')
        for n in ('events.json','intelligence.json'):(d/n).write_text('{}')
        for n in ('feed.xml','watchlist.xml'):(d/n).write_text('<rss/>')
        (d/'assets').mkdir();(d/'assets/test.js').write_text('/* test */')
        (self.root/'site').mkdir();(self.root/'site/obsolete.html').write_text('old')
    def test_build_replaces_stale_output(self):
        out=build_site(self.root,Fake(),'https://example.invalid/')
        self.assertFalse((out/'obsolete.html').exists());self.assertTrue((out/'hardware-search.html').exists());self.assertEqual((out/'assets/test.js').read_text(),'/* test */')
    def test_build_failure_preserves_previous_site(self):
        for gen in (Fake(fail=True),Fake(incomplete=True)):
            with self.assertRaises(RuntimeError):build_site(self.root,gen,'https://example.invalid/')
            self.assertTrue((self.root/'site/obsolete.html').exists())
    def test_native_config_and_cli(self):
        with patch('generators.zensical.subprocess.run') as run:
            g=get_generator({'native_search':False});g.render(ROOT,self.root,'https://example.invalid/')
            cfg=tomllib.loads((self.root/'zensical.toml').read_text())['project'];self.assertFalse(cfg['plugins']['search']['enabled']);self.assertFalse(cfg['use_directory_urls']);self.assertEqual(cfg['site_url'],'https://example.invalid/');self.assertIn('--strict',run.call_args.args[0]);self.assertIn('--clean',run.call_args.args[0]);self.assertTrue(run.call_args.kwargs['check'])
        with self.assertRaises(ValueError):get_generator({'engine':'missing'})
