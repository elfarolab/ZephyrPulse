import datetime as dt
import os
import unittest
from unittest.mock import patch

import test_pulse
from pulse import collect, first_parent_window, UTC
from intelligence import inventory, update_history


class GitHistoryCompatibilityTest(unittest.TestCase):
    setUp = test_pulse.PulseTest.setUp
    git = test_pulse.PulseTest.git
    put = test_pulse.PulseTest.put
    commit = test_pulse.PulseTest.commit

    def dated_commit(self, filename, stamp):
        self.put('doc/' + filename + '.rst', filename)
        with patch.dict(os.environ, {'GIT_AUTHOR_DATE': stamp, 'GIT_COMMITTER_DATE': stamp}):
            return self.commit(filename)

    def test_both_collectors_work_without_modern_date_option(self):
        now = dt.datetime.now(UTC).replace(microsecond=0)
        # Newer parent behind an old-dated child; normal --since can miss it.
        boundary = self.dated_commit('boundary', (now-dt.timedelta(days=3)).isoformat())
        recent = self.dated_commit('recent', (now-dt.timedelta(days=1)).isoformat())
        old = self.dated_commit('old', (now-dt.timedelta(days=10)).isoformat())
        head = self.dated_commit('head', now.isoformat())
        original = self.g.git
        def legacy_git(*args, **kwargs):
            if any(a.startswith('--since-as-filter') for a in args):
                raise RuntimeError('git exited 129: unsupported option')
            return original(*args, **kwargs)
        with patch.object(self.g, 'git', side_effect=legacy_git):
            rows = first_parent_window(self.g, head, (now-dt.timedelta(days=3)).isoformat())
            self.assertEqual([sha for sha, _, _ in rows], [head, recent, boundary, self.base])
            collect(self.db,self.g,head,now,72)
            actual={r[0] for r in self.db.execute('SELECT sha FROM commits')}
            self.assertEqual(actual,{head,recent,boundary,self.base})
            boards=inventory(self.g,head)
            coverage=update_history(self.db,self.g,head,now,boards,90,0)
            self.assertTrue(coverage['complete'])
            self.assertEqual({r[0] for r in self.db.execute('SELECT sha FROM history_seen')}, actual|{old})
            # Repeated collection preserves the same events and checkpoint.
            collect(self.db,self.g,head,now,72)
            self.assertEqual({r[0] for r in self.db.execute('SELECT sha FROM commits')},actual)

    def test_timezone_and_exact_boundary(self):
        now=dt.datetime.now(UTC).replace(microsecond=0)
        cutoff=now-dt.timedelta(days=3)
        before=self.dated_commit('before',(cutoff-dt.timedelta(seconds=1)).isoformat())
        exact=self.dated_commit('exact',cutoff.astimezone(dt.timezone(dt.timedelta(hours=9))).isoformat())
        rows=first_parent_window(self.g,exact,cutoff.isoformat())
        by_sha={sha:date for sha,date,_ in rows}
        self.assertNotIn(before,by_sha)
        self.assertEqual(by_sha[exact],cutoff.isoformat(timespec='seconds'))

if __name__ == '__main__':
    unittest.main()
