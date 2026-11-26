import datetime as dt
import unittest
import test_pulse
from pulse import UTC
from intelligence import inventory, release_tags, tracked_releases, release_status
from comparison import release_snapshots

class ReleaseScopeTests(unittest.TestCase):
    setUp = test_pulse.PulseTest.setUp
    git = test_pulse.PulseTest.git
    put = test_pulse.PulseTest.put
    commit = test_pulse.PulseTest.commit

    def test_latest_and_rollover(self):
        for tag in ('v2.7.6','v2.7.99','v3.7.2','v4.4.2','v4.5.0','v4.5.99','v4.6.0-rc1'):
            self.git('tag',tag,self.base)
        cfg={'lts_series':['2.7','3.7'], 'release_policy':{'series':{'2.7':{},'3.7':{},'4.5':{}}}}
        tags,policy=tracked_releases(self.g,cfg)
        self.assertEqual([x['tag'] for x in tags],['v4.5.0'])
        self.assertEqual(list(policy['series']),['4.5'])
        self.assertNotIn('v2.7.99',[x['tag'] for x in release_tags(self.g,set())])
        self.put('doc/new.rst','new'); head=self.commit('new development')
        status=release_status(self.g,self.db,tags,[head,self.base])
        self.assertEqual(status[head]['status'],'main_only')
        self.assertEqual(status[self.base]['first_release'],'v4.5.0')
        self.assertEqual(status[self.base]['lts_tags'],[])
        self.git('tag','v4.6.0',head)
        tags,_=tracked_releases(self.g,cfg)
        self.assertEqual([x['tag'] for x in tags],['v4.6.0'])
        self.assertEqual(release_status(self.g,self.db,tags,[head])[head]['first_release'],'v4.6.0')
        self.git('tag','v4.6.10',head); self.git('tag','v4.6.9',head)
        self.assertEqual(tracked_releases(self.g,cfg)[0][-1]['tag'],'v4.6.10')

    def test_optional_lts_and_pruning(self):
        for tag in ('v2.7.6','v2.7.99','v3.7.2','v4.5.0'):
            self.git('tag',tag,self.base)
        cfg={'release_tracking':'latest_and_lts','lts_series':['2.7','3.7']}
        tags,policy=tracked_releases(self.g,cfg)
        self.assertEqual([x['tag'] for x in tags],['v2.7.6','v3.7.2','v4.5.0'])
        boards=inventory(self.g,self.base,self.db); now=dt.datetime.now(UTC)
        release_snapshots(self.g,tags,boards,policy,now,self.db)
        tags,policy=tracked_releases(self.g,{})
        self.assertEqual([x['tag'] for x in release_snapshots(self.g,tags,boards,policy,now,self.db)],['v4.5.0'])
        keys=[r[0] for r in self.db.execute("SELECT key FROM performance_cache WHERE key LIKE 'release-snapshot:%'")]
        self.assertEqual(keys,['release-snapshot:v4.5.0'])

    def test_no_final_tags(self):
        self.git('tag','v4.5.99',self.base); self.git('tag','v4.6.0-rc1',self.base)
        tags,policy=tracked_releases(self.g,{})
        self.assertEqual(tags,[])
        self.assertEqual(release_status(self.g,self.db,tags,[self.base])[self.base]['status'],'unknown')
        with self.assertRaises(ValueError): tracked_releases(self.g,{'release_tracking':'typo'})
