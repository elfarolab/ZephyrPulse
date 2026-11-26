import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from configuration import load_config
from browser_data import publish_catalog
from generators import get_generator, build_site
from test_generators import Fake, ROOT
import test_generators
from intelligence import release_status, release_tags
import test_pulse

class NewFeatures(TestCase):
    def test_merge_and_explicit_empty_lists(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'config.yml').write_text('generator: {engine: zensical, strict: true}\nwatchlist: {boards: [kit], vendors: [nxp]}\nsite_url: http://localhost/\n')
            (root/'config.local.yml').write_text('generator: {native_search: false}\nwatchlist: {boards: []}\nsite_url: https://example.invalid/\n')
            c=load_config(root)
            self.assertEqual(c['generator'],{'engine':'zensical','strict':True,'native_search':False})
            self.assertEqual(c['watchlist'],{'boards':[],'vendors':['nxp']})
            self.assertEqual(load_config(root,root/'config.yml')['site_url'],'http://localhost/')
            (root/'config.local.yml').write_text('bad: [')
            with self.assertRaises(Exception):load_config(root)

    def test_catalog_unchanged_when_activity_changes(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            def run(n):
                comparison={'snapshots':[],'targets':[{'id':'kit','board_id':'kit','metadata':{'features':['can'],'dts_evidence':{}},'releases':[],'vendor_commits':n,'milestone_count':n}]}
                payload={'updated':str(n),'head':str(n),'boards':[{'id':'kit','last_activity':str(n)}],'events':[{'subject':str(n),'boards':['kit']}],'vendors':[{'vendor':'test','commits':n}]}
                publish_catalog(root,comparison,payload)
            run(1); first=(root/'intelligence.json').read_bytes();dynamic=(root/'data/activity.json').read_bytes()
            run(2);self.assertEqual(first,(root/'intelligence.json').read_bytes());self.assertNotEqual(dynamic,(root/'data/activity.json').read_bytes())
            self.assertEqual(json.loads((root/'data/news-view.json').read_text())['events'][0]['subject'],'2')
            self.assertEqual(json.loads((root/'data/activity.json').read_text())['target_activity']['kit']['milestone_count'],2)

class CachedRendererTests(TestCase):
    setUp=test_generators.GeneratorTests.setUp
    # Use the existing fixture setup; simulate Zensical to verify orchestration only.
    def test_incremental_reuses_inputs_and_falls_back(self):
        (self.root/'zensical.toml').write_bytes((ROOT/'zensical.toml').read_bytes())
        g=get_generator({'incremental':True,'native_search':False});calls=[]
        def fake_run(work,text,clean):
            calls.append((work,clean))
            if (work/'site').exists():
                import shutil;shutil.rmtree(work/'site')
            Fake().render(self.root,work,'https://example.invalid/')
        with patch.object(g,'_run',side_effect=fake_run):
            build_site(self.root,g,'https://example.invalid/')
            stable=self.root/'.pulse-render-cache/docs/boards.md';stamp=stable.stat().st_mtime_ns
            (self.root/'docs/index.md').write_text('new content')
            build_site(self.root,g,'https://example.invalid/')
            self.assertEqual(stamp,stable.stat().st_mtime_ns)
            self.assertEqual([x[1] for x in calls],[True,False])
        def failure(work,text,clean):
            if work.name=='.pulse-render-cache':raise RuntimeError('cache failure')
            fake_run(work,text,clean)
        with patch.object(g,'_run',side_effect=failure):
            build_site(self.root,g,'https://example.invalid/')
        self.assertFalse((self.root/'.pulse-render-cache').exists());self.assertTrue((self.root/'site/index.html').exists())

class BatchReleaseTests(TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit
    def test_batched_results_equal_individual_queries(self):
        self.git('tag','v4.0.0',self.base)
        shas=[self.base]
        for i in range(9):
            self.put('doc/test.rst',str(i));shas.append(self.commit('test '+str(i)))
        self.git('tag','v4.1.0',shas[3])
        tags=release_tags(self.g,{'4.1'})
        batch=release_status(self.g,self.db,tags,shas)
        self.db.execute('DELETE FROM release_cache');self.db.commit()
        individual={sha:release_status(self.g,self.db,tags,[sha])[sha] for sha in shas}
        self.assertEqual(batch,individual)
