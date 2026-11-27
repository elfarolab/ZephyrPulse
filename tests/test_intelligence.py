import datetime as dt
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_pulse
from pulse import collect, render, UTC
from intelligence import inventory, update_history, release_tags, release_status, render_extra, match_pattern, watch_match, get_prs

class IntelligenceTest(unittest.TestCase):
    setUp = test_pulse.PulseTest.setUp
    git = test_pulse.PulseTest.git
    put = test_pulse.PulseTest.put
    commit = test_pulse.PulseTest.commit
    def test_inventory_watch_and_render(self):
        self.put(self.board+'board.yml','board:\n  name: kit\n  full_name: ACME Kit\n  vendor: acme\n  socs:\n    - name: RA8P1\n')
        self.put(self.board+'kit.yaml','identifier: kit/RA8P1\narch: arm\nsupported: [gpio, can]\n')
        self.put('boards/nxp/frdm_mcxn947/board.yml','board:\n  name: frdm_mcxn947\n  socs:\n    - name: mcxn947\n')
        self.put('boards/other/unwatched/board.yml','board:\n  name: unwatched\n  socs:\n    - name: unrelated\n')
        sha=self.commit('add new boards and CAN'); now=dt.datetime.now(UTC)
        collect(self.db,self.g,sha,now,72); boards=inventory(self.g,sha)
        self.assertEqual(len(boards),3)
        key=next(k for k in boards if boards[k]['name']=='kit')
        self.assertIn('can',boards[key]['metadata']['kit/RA8P1']['features'])
        coverage=update_history(self.db,self.g,sha,now,boards,90,0); self.assertTrue(coverage['complete'])
        self.git('tag','v4.0.0',sha); self.git('tag','v4.1.0-rc1',sha); self.git('tag','v3.7.9',self.base)
        tags=release_tags(self.g,{'3.7'}); self.assertEqual([x['tag'] for x in tags],['v3.7.9','v4.0.0'])
        statuses=release_status(self.g,self.db,tags,[sha,self.base]); self.assertEqual(statuses[sha]['first_release'],'v4.0.0'); self.assertEqual(statuses[self.base]['lts_tags'],['v3.7.9'])
        watch={'boards':['*mcxn*','ra8P1']}; self.assertTrue(match_pattern('frdm_mcxn947','*MCXN*')); self.assertTrue(match_pattern('renesas/ra8p1','ra8P1')); self.assertTrue(match_pattern('mcxn947','mcxn94[57]')); self.assertFalse(match_pattern('other','*mcxn*'))
        self.assertTrue(watch_match({'boards':[key],'subject':'kit'},boards,watch))
        docs=self.root/'docs'; render(self.db,docs,now,72,'https://example.invalid/',statuses)
        render_extra(self.db,docs,now,sha,boards,coverage,tags,{'status':'disabled','items':[]},statuses,watch,'https://example.invalid/')
        data=json.loads((docs/'intelligence.json').read_text()); self.assertEqual(len(data['boards']),3)
        self.assertIn('unwatched',(docs/'board.md').read_text()); self.assertNotIn('pulse-category-summary',(docs/'index.md').read_text()); self.assertIn('Watchlist highlights',(docs/'index.md').read_text()); self.assertIn('unwatched',(docs/'boards.md').read_text()); self.assertNotIn('unwatched',(docs/'watchlist.md').read_text())
        self.assertTrue((docs/'watchlist.xml').exists()); self.assertIn('Declared',(docs/'boards'/f"{boards[key]['slug']}.md").read_text())
        # JSON and static page include release metadata; browser filtering doesn't alter global events.
        self.assertTrue(any(x['watched'] for x in json.loads((docs/'data/news-view.json').read_text())['events'])); self.assertTrue(any(not x['watched'] for x in json.loads((docs/'data/news-view.json').read_text())['events']))
        self.assertIn('v4.0.0',(docs/'releases.md').read_text())
        events=json.loads((docs/'data/news-view.json').read_text())['events']
        self.assertTrue(any(e.get('board_profile_url')=='boards/'+boards[key]['slug']+'.html' for e in events))
        self.assertIn('boards/'+boards[key]['slug']+'.html',(docs/'releases.md').read_text())
        self.assertEqual((docs/'index.md').read_text().count('class="pulse-stat-label"'),10)
        self.assertNotIn('<!-- pulse-watchlist-slot -->',(docs/'index.md').read_text())
    def test_history_retention_and_rewrite(self):
        now=dt.datetime.now(UTC); collect(self.db,self.g,self.base,now,72); boards=inventory(self.g,self.base)
        update_history(self.db,self.g,self.base,now,boards,90,0)
        count=self.db.execute('SELECT count(*) FROM milestones').fetchone()[0]; self.assertGreater(count,0)
        future=now+dt.timedelta(days=4); collect(self.db,self.g,self.base,future,72); update_history(self.db,self.g,self.base,future,boards,90,0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0); self.assertEqual(self.db.execute('SELECT count(*) FROM milestones').fetchone()[0],count)
        self.put(self.board+'kit.yaml','identifier: kit/chip\nsupported: [gpio, adc]\n'); orphan=self.commit('add ADC'); collect(self.db,self.g,orphan,now,72); update_history(self.db,self.g,orphan,now,inventory(self.g,orphan),90,0)
        self.assertTrue(self.db.execute('SELECT 1 FROM history_seen WHERE sha=?',(orphan,)).fetchone())
        self.git('reset','--hard',self.base); collect(self.db,self.g,self.base,now,72); update_history(self.db,self.g,self.base,now,boards,90,0)
        self.assertFalse(self.db.execute('SELECT 1 FROM history_seen WHERE sha=?',(orphan,)).fetchone())
        far=now+dt.timedelta(days=91); collect(self.db,self.g,self.base,far,72); update_history(self.db,self.g,self.base,far,boards,90,0); self.assertEqual(self.db.execute('SELECT count(*) FROM history_seen').fetchone()[0],0)
    def test_release_cache_invalidation(self):
        now=dt.datetime.now(UTC); self.git('tag','v4.0.0',self.base)
        self.put('doc/new.rst','new'); sha=self.commit('new'); collect(self.db,self.g,sha,now,72)
        tags=release_tags(self.g,{'4.1'}); self.assertEqual(release_status(self.g,self.db,tags,[sha])[sha]['status'],'main_only')
        self.git('tag','v4.1.0',sha); tags=release_tags(self.g,{'4.1'}); self.assertEqual(release_status(self.g,self.db,tags,[sha])[sha]['lts_tags'],['v4.1.0'])
    def test_pr_failure_is_stale(self):
        now=dt.datetime.now(UTC); self.db.execute('INSERT INTO state VALUES(?,?)',('pr_snapshot',json.dumps({'status':'ok','items':[{'number':1}],'scanned':1}))); self.db.commit()
        with patch('intelligence.urlopen',side_effect=URLError('offline')):
            self.assertEqual(get_prs(self.db,{},now)['status'],'stale')
        self.assertEqual(get_prs(self.db,{'pull_requests':{'enabled':False}},now)['status'],'disabled')
    def test_bounded_backfill(self):
        now=dt.datetime.now(UTC)
        for i in range(3): self.put('doc/history.rst',str(i)); sha=self.commit(f'change {i}')
        later=now+dt.timedelta(days=4); collect(self.db,self.g,sha,later,72); boards=inventory(self.g,sha)
        c=update_history(self.db,self.g,sha,later,boards,90,1); self.assertEqual(c['processed'],1); self.assertFalse(c['complete'])
        c=update_history(self.db,self.g,sha,later,boards,90,0); self.assertTrue(c['complete']); self.assertEqual(c['processed'],4)
