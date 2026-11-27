"""Conservative renderer bypass and content-driven publication regressions."""
import datetime as dt
import io
import json
import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from generators import build_site, get_generator
from test_generators import Fake, ROOT
import test_generators
from pulse import UTC, collect, render
from intelligence import inventory, render_extra, update_history, get_prs
from news_groups import recent_files
import test_pulse


class FastRendererTests(TestCase):
    setUp = test_generators.GeneratorTests.setUp

    def prepare(self, native=False):
        shutil.copyfile(ROOT/'zensical.toml', self.root/'zensical.toml')
        return get_generator({'incremental':True,'native_search':native})

    def fake_run(self, work, text, clean):
        if (work/'site').exists(): shutil.rmtree(work/'site')
        Fake().render(self.root,work,'https://example.invalid/')

    def test_only_data_and_no_changes_skip_renderer(self):
        g=self.prepare(); docs=self.root/'docs'; (docs/'data').mkdir()
        (docs/'data/old.json').write_text('{}')
        with patch.object(g,'_run',side_effect=self.fake_run) as run:
            out=build_site(self.root,g,'https://example.invalid/')
            before=(out/'index.html').read_bytes()
            (docs/'data/old.json').unlink(); (docs/'data/status.json').write_text('{"updated":"new"}')
            (docs/'events.json').write_text('{"events":[]}')
            with self.assertLogs(level='INFO') as logs:
                build_site(self.root,g,'https://example.invalid/')
            self.assertIn('renderer skipped', '\n'.join(logs.output))
            self.assertEqual(run.call_count,1)
            self.assertEqual((out/'index.html').read_bytes(),before)
            self.assertFalse((out/'data/old.json').exists())
            self.assertEqual((out/'events.json').read_bytes(),(docs/'events.json').read_bytes())
            build_site(self.root,g,'https://example.invalid/');self.assertEqual(run.call_count,1)
            (docs/'index.md').write_text('changed Markdown')
            build_site(self.root,g,'https://example.invalid/');self.assertEqual(run.call_count,2)
            (docs/'assets/test.js').write_text('changed JS')
            build_site(self.root,g,'https://example.invalid/');self.assertEqual(run.call_count,3)
            build_site(self.root,g,'https://other.invalid/');self.assertEqual(run.call_count,4)

    def test_native_search_and_invalid_cache(self):
        g=self.prepare(native=True)
        with patch.object(g,'_run',side_effect=self.fake_run) as run:
            build_site(self.root,g,'https://example.invalid/');build_site(self.root,g,'https://example.invalid/')
            self.assertEqual(run.call_count,2)
        g=self.prepare()
        with patch.object(g,'_run',side_effect=self.fake_run) as run:
            build_site(self.root,g,'https://example.invalid/')
            (self.root/'.pulse-render-cache/site/index.html').unlink()
            with self.assertLogs(level='ERROR'):
                out=build_site(self.root,g,'https://example.invalid/')
            self.assertEqual(run.call_count,2);self.assertTrue((out/'index.html').exists())


class StableContentTests(TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit

    def test_collection_time_only_and_expiry(self):
        docs=self.root/'docs'; now=dt.datetime.now(UTC).replace(hour=12,minute=0,second=0,microsecond=0)
        if now<dt.datetime.now(UTC): now+=dt.timedelta(days=1)
        def cycle(t):
            collect(self.db,self.g,self.base,t,72)
            boards=inventory(self.g,self.base,self.db)
            cov=update_history(self.db,self.g,self.base,t,boards,90,0)
            files=recent_files(self.db,self.g)
            render(self.db,docs,t,72,'https://example.invalid/',boards=boards,dynamic_news=True,commit_files=files,write_events=False)
            render_extra(self.db,docs,t,self.base,boards,cov,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/',commit_files=files,dynamic_news=True)
        def tree():return {p.relative_to(docs).as_posix():p.read_bytes() for p in docs.rglob('*') if p.is_file()}
        cycle(now); before=tree(); cycle(now+dt.timedelta(minutes=15)); after=tree()
        self.assertEqual({k for k in before if before[k]!=after[k]},{'data/status.json'})
        self.assertEqual(json.loads(after['data/status.json'])['updated'],(now+dt.timedelta(minutes=15)).isoformat())
        cycle(now+dt.timedelta(days=4)); final=tree()
        self.assertNotEqual(after['events.json'],final['events.json'])
        self.assertNotEqual(after['data/news-view.json'],final['data/news-view.json'])
        self.assertEqual(json.loads(final['events.json'])['events'],[])
        self.assertNotEqual(after['index.md'],final['index.md'])

    def test_pr_interval_and_config_change(self):
        now=dt.datetime.now(UTC)
        class Response(io.StringIO):
            headers={}
        with patch('intelligence.urlopen',side_effect=lambda *a,**k:Response('[]')) as request:
            cfg={'pull_requests':{'refresh_minutes':60}}
            first=get_prs(self.db,cfg,now)
            self.assertEqual(get_prs(self.db,cfg,now+dt.timedelta(minutes=15)),first)
            self.assertEqual(request.call_count,1)
            get_prs(self.db,cfg,now+dt.timedelta(minutes=60));self.assertEqual(request.call_count,2)
            get_prs(self.db,{**cfg,'branch':'other'},now+dt.timedelta(minutes=61));self.assertEqual(request.call_count,3)
            get_prs(self.db,{'branch':'other','pull_requests':{'refresh_minutes':0}},now+dt.timedelta(minutes=62));self.assertEqual(request.call_count,4)
