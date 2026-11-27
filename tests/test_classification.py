"""Git-backed classification and in-place migration regressions."""
import datetime as dt
import json
from unittest import TestCase
from unittest.mock import patch
import test_pulse
from pulse import collect, render, UTC, connect
from intelligence import inventory, update_history, render_extra
from classification import VERSION
from news_table import render_news_table


class ClassificationTests(TestCase):
    setUp = test_pulse.PulseTest.setUp
    git = test_pulse.PulseTest.git
    put = test_pulse.PulseTest.put
    commit = test_pulse.PulseTest.commit
    events = test_pulse.PulseTest.events

    def collect_head(self, head):
        collect(self.db,self.g,head,dt.datetime.now(UTC),72)
        return self.events(head)

    def test_exact_devicetree_example_and_real_api_change(self):
        path='include/zephyr/devicetree.h'
        self.put(path,'/**\n * @param status a status as one of the tokens okay or disabled, not a string\n */\n#define DT_NODE_HAS_STATUS(x,y) (x)\n')
        self.commit('initial API')
        self.put(path,'/**\n * @param status a status as one of the tokens okay, disabled or reserved, not a string\n */\n#define DT_NODE_HAS_STATUS(x,y) (x)\n')
        sha=self.commit('dts: extend DT_NODE_HAS_STATUS to include reserved')
        events=self.collect_head(sha)
        self.assertEqual(len(events),1)
        e=events[0]; self.assertEqual((e['kind'],e['subject'],e['change_type'],e['confidence'],e['path'],e['source_revision']),('dts','DT_NODE_HAS_STATUS','API documentation','observed',path,sha))
        self.assertIn('no implementation change detected',e['detail'])
        self.put(path,'/**\n * @param status new semantics\n */\n#define DT_NODE_HAS_STATUS(x,y) (y)\n')
        sha=self.commit('dts: change DT_NODE_HAS_STATUS'); self.assertEqual(self.collect_head(sha)[0]['change_type'],'API change')

    def test_existing_subsystem_changes_and_no_fake_milestones(self):
        paths={'drivers/adc/acme/adc.c':'driver','drivers/sensor/acme/temp.c':'sensor','soc/acme/chip/clock.c':'soc','dts/bindings/sensor/acme,temp123.yaml':'dt_bindings','scripts/dts/gen_defines.py':'dts','doc/existing.rst':'docs',self.board+'Kconfig.kit':'board_change'}
        for p in paths:
            if p.endswith('.yaml'): continue
            self.put(p,'old\n')
        self.commit('initial sources')
        for p in paths: self.put(p,'compatible: "acme,temp123"\nproperties: {}\n' if p.endswith('.yaml') else 'updated\n')
        sha=self.commit('fix existing sources'); events=self.collect_head(sha)
        self.assertEqual({e['path']:e['kind'] for e in events},paths)
        self.assertTrue(all(e['confidence']=='observed' for e in events))
        self.assertEqual(next(e for e in events if 'bindings' in e['path'])['change_type'],'Binding change')
        self.assertEqual(next(e for e in events if 'scripts' in e['path'])['change_type'],'Tooling change')
        now=dt.datetime.now(UTC); boards=inventory(self.g,sha); update_history(self.db,self.g,sha,now,boards,90,0)
        self.assertFalse(self.db.execute('SELECT 1 FROM milestones WHERE sha=?',(sha,)).fetchone())
        self.assertFalse(self.db.execute("SELECT 1 FROM vendor_activity WHERE sha=? AND signal IN ('driver','sensor')",(sha,)).fetchone())
        self.assertTrue(self.db.execute("SELECT 1 FROM vendor_activity WHERE sha=? AND signal='driver_changes'",(sha,)).fetchone())
        docs=self.root/'docs'; render(self.db,docs,now,72,'https://example.invalid/',boards=boards,dynamic_news=True)
        render_extra(self.db,docs,now,sha,boards,{'days':90,'processed':3,'total':3,'complete':True},[],{'status':'disabled','items':[]},{},{},'https://example.invalid/')
        self.assertIn('data-pulse-category="board_change"',(docs/'board_change.md').read_text())
        self.assertIn('Board maintenance',(docs/'index.md').read_text())
        rows=json.loads((docs/'data/news-view.json').read_text())['events']; self.assertTrue(any(e['change_type']=='Binding change' for e in rows))

    def test_source_links_and_prefix_priority(self):
        self.put('subsys/misc/a.c','a'); sha=self.commit('dts: unknown path'); e=self.collect_head(sha)[0]; self.assertEqual((e['kind'],e['confidence'],e['path']),('subsys','observed','subsys/misc/a.c'))
        self.put('drivers/adc/a.c','a'); sha=self.commit('dts: misleading prefix'); self.assertEqual(self.collect_head(sha)[0]['kind'],'driver')
        self.put('subsys/misc/a.c','b'); sha=self.commit('unrelated change'); e=self.collect_head(sha)[0]; self.assertEqual((e['kind'],e['path']),('subsys','subsys/misc/a.c'))
        self.git('rm','subsys/misc/a.c'); removed=self.commit('remove unused code'); e=self.collect_head(removed)[0]; self.assertEqual(e['source_revision'],sha)
        e.update(committed='2026-11-27T02:28:00Z'); html=render_news_table([e]); self.assertIn('/blob/'+sha+'/subsys/misc/a.c',html); self.assertIn('before removal',html)
        self.git('commit','--allow-empty','-m','empty commit'); empty=self.git('rev-parse','HEAD'); self.assertEqual(self.collect_head(empty)[0]['path'],'')

    def test_new_categories_path_priority_and_migration(self):
        from pulse import DISPLAY_CATEGORIES
        from news_groups import recent_files, group_events
        from classification import prefix_category
        paths = {
            'samples/drivers/gpio/sample.yaml': ('samples','name: example'),
            'samples/sensor/example/board.overlay': ('samples','&gpio0 {};'),
            'tests/lib/devicetree/test.c': ('tests','/* test */'),
            'subsys/net/lib/sockets/socket.c': ('subsys','/* socket */'),
            'include/zephyr/dt-bindings/gpio/example.h': ('dt_bindings','#define FLAG 1'),
            'dts/bindings/gpio/example.yaml': ('dt_bindings','compatible: "example,gpio"'),
            'west.yml': ('manifest','manifest:\n  projects: []'),
            'kernel/example.c': ('kernel','/* kernel */'),
            'arch/arm/arch_example.c': ('kernel','/* arch */'),
        }
        self.assertIsNone(prefix_category('west: update command implementation'))
        for path, (_, content) in paths.items(): self.put(path,content)
        sha=self.commit('drivers: deliberately misleading title')
        events=self.collect_head(sha)
        self.assertEqual({e['path']:e['kind'] for e in events}, {p:k for p,(k,_) in paths.items()})
        self.assertTrue(all(e['confidence']=='observed' for e in events))
        # Simulate the old retained classification and trigger migration without a new commit.
        with self.db:
            self.db.execute("UPDATE state SET value='1' WHERE key='news_classifier_version'")
            self.db.execute("UPDATE events SET kind='other' WHERE sha=?",(sha,))
        self.assertEqual(self.collect_head(sha),events)
        docs=self.root/'docs'; manifests=recent_files(self.db,self.g)
        render(self.db,docs,dt.datetime.now(UTC),72,'https://example.invalid/',commit_files=manifests)
        self.assertEqual(len(DISPLAY_CATEGORIES),15)
        home=(docs/'index.md').read_text()
        self.assertIn('href="kernel.html"',home); self.assertNotIn('href="board_candidate.html"',home)
        self.assertIn('data-pulse-legacy-board-candidate',(docs/'board_candidate.md').read_text())
        for kind in {k for k,_ in paths.values()}:
            self.assertEqual(len(group_events([e for e in events if e['kind']==kind],kind)),1)
            text=(docs/(kind+'.md')).read_text()
            self.assertIn('Affected files (9) — complete commit',text)
            self.assertIn('data-news-column="4">Files',text)
            self.assertNotIn('data-news-column="1"',text)
        self.put('scripts/west_commands/example.py','print(1)')
        tooling=self.commit('west: update command implementation')
        self.assertEqual(self.collect_head(tooling)[0]['kind'],'other')

    def test_semantic_events_not_duplicated(self):
        self.put('drivers/adc/acme_adc.c','#define DT_DRV_COMPAT acme_adc\n'); sha=self.commit('drivers: new ADC'); events=self.collect_head(sha)
        self.assertEqual(len([e for e in events if e['kind']=='driver']),1)
        self.assertEqual(events[0]['change_type'],'Driver compatible')

    def test_recent_migration_atomic_and_idempotent(self):
        self.put('include/zephyr/devicetree.h','#define DT_X 1\n'); sha=self.commit('dts: new API'); self.collect_head(sha)
        with self.db:
            self.db.execute("UPDATE state SET value='old' WHERE key='news_classifier_version'")
            self.db.execute("UPDATE events SET kind='other',path='',change_type='' WHERE sha=?",(sha,))
        with patch('pulse.classify',side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError): self.collect_head(sha)
        self.assertEqual(self.events(sha)[0]['kind'],'other')
        events=self.collect_head(sha); self.assertEqual(events[0]['kind'],'dts')
        with patch('pulse.classify',side_effect=AssertionError('no repeat migration')): self.assertEqual(self.collect_head(sha),events)
        self.assertEqual(self.db.execute("SELECT value FROM state WHERE key='news_classifier_version'").fetchone()[0],VERSION)

    def test_historical_refresh_bounded_and_preserves_coverage(self):
        self.put('doc/a.rst','a'); head=self.commit('doc'); now=dt.datetime.now(UTC)+dt.timedelta(days=4)
        collect(self.db,self.g,head,now,72); boards=inventory(self.g,head)
        update_history(self.db,self.g,head,now,boards,90,0)
        with self.db: self.db.execute("UPDATE history_seen SET classifier_version='old'")
        before=self.db.execute('SELECT count(*) FROM milestones').fetchone()[0]
        coverage=update_history(self.db,self.g,head,now,boards,90,1)
        self.assertEqual((coverage['processed'],coverage['classification_pending']),(2,1))
        self.assertEqual(self.db.execute('SELECT count(*) FROM milestones').fetchone()[0],before)
        coverage=update_history(self.db,self.g,head,now,boards,90,1)
        self.assertEqual(coverage['classification_pending'],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM history_seen').fetchone()[0],2)

    def test_legacy_schema_additive_migration(self):
        import sqlite3
        from pulse import SCHEMA
        path=self.root/'legacy.sqlite'
        with sqlite3.connect(path) as old:
            old.executescript(SCHEMA)
            old.execute('INSERT INTO commits VALUES(?,?,?)',(self.base,'2026-11-26T00:00:00+00:00','legacy'))
            old.execute("INSERT INTO events(sha,kind,subject,detail,confidence,path) VALUES(?,?,?,?,?,?)",(self.base,'other','legacy','old','unclassified',''))
        db=connect(path); self.addCleanup(db.close)
        row=db.execute('SELECT * FROM events').fetchone()
        self.assertEqual((row['subject'],row['change_type'],row['source_revision']),('legacy','',''))
        self.assertEqual(db.execute('SELECT count(*) FROM commits').fetchone()[0],1)
