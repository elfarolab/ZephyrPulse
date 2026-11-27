"""Commit-level presentation: raw events and exact Git files remain independent."""
from unittest import TestCase
from unittest.mock import patch
from news_groups import group_events, recent_files, manifest_files
from news_table import render_grouped_news
import test_pulse
import datetime as dt
from pulse import UTC, collect


def event(sha='a'*40, path='drivers/i2c/i2c_omap.c', **kw):
    return dict(dict(sha=sha, kind='driver', subject=path.rsplit('/',1)[-1], path=path,
                     commit_subject='drivers: i2c: omap: add I2C target mode support',
                     detail='Driver change', confidence='observed', change_type='Driver change',
                     committed='2026-11-27T02:26:00Z'), **kw)


class GroupTests(TestCase):
    def test_driver_group_and_full_manifest(self):
        a=event(); b=event(path='drivers/i2c/Kconfig.omap'); c=event(sha='b'*40,path=b['path'])
        rows=[a,b,c,dict(a,detail='Second signal')]
        groups=group_events(rows,'driver')
        self.assertEqual(len(groups),2)
        self.assertEqual((groups[0]['subsystem'],groups[0]['driver']),('i2c','omap'))
        self.assertEqual(len(groups[0]['files']),2)
        manifest=[dict(path=x, revision=a['sha'], status='M') for x in [a['path'],b['path'],'doc/a b.rst']]
        html=render_grouped_news(rows,'driver',commit_files={a['sha']:manifest})
        self.assertEqual(html.count('class="pulse-news-row '),2)
        self.assertIn('Affected files (3) — complete commit',html)
        self.assertIn('Known evidence files (1) — complete diff unavailable',html)
        self.assertIn('doc/a%20b.rst',html)
        self.assertIn('Second signal',html)
        self.assertNotIn('pulse-subject-filter',html)
        self.assertIn('data-sort-value="3"',html)
        self.assertIn('hardware-search.html?subject='+a['sha'],html)
        self.assertEqual(len(rows),4)

    def test_scoped_categories_and_generic_names(self):
        self.assertEqual(group_events([event(path='drivers/pcie/CMakeLists.txt')],'driver')[0]['driver'],'Subsystem-level / not identified')
        self.assertEqual(group_events([event(path='drivers/timer/ite_it8xxx2_timer.c')],'driver')[0]['driver'],'ite_it8xxx2')
        rows=[event(kind='soc',path='soc/acme/chip/a.c'),event(kind='soc',path='soc/acme/chip/b.c'),event(kind='soc',path='soc/other/chip/a.c')]
        self.assertEqual(len(group_events(rows,'soc')),2)
        self.assertEqual(group_events(rows,'soc')[0]['subject'],'soc/acme/chip')
        rows=[event(kind='board_change',path='boards/a/kit/a.c',subject='kit'),event(kind='board_change',path='boards/b/kit/a.c',subject='kit')]
        self.assertEqual(len(group_events(rows,'board_change')),2)
        for kind in ('docs','other','sensor','dts'):
            self.assertEqual(len(group_events([event(kind=kind),event(kind=kind,path='another')],kind)),1)

    def test_escape_and_deleted_revision(self):
        e=event(path='drivers/i2c/<bad>.c',detail='<script>x</script>',source_revision='b'*40)
        manifest=[dict(path=e['path'],revision=e['source_revision'],status='D')]
        html=render_grouped_news([e],'driver',commit_files={e['sha']:manifest})
        self.assertIn('/blob/'+'b'*40+'/drivers/i2c/%3Cbad%3E.c',html)
        self.assertIn('Deleted',html);self.assertIn('before removal',html)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)


class GitManifestTests(TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit

    def test_exact_diff_cache_and_removal(self):
        p='drivers/i2c/i2c_omap.c';q='drivers/i2c/Kconfig.omap';extra='doc/extra.rst'
        self.put(p,'source');self.put(q,'config');self.put(extra,'doc')
        a=self.commit('drivers: i2c: omap: add support')
        now=dt.datetime.now(UTC);collect(self.db,self.g,a,now,72)
        manifest=recent_files(self.db,self.g)
        self.assertEqual({x['path'] for x in manifest[a]},{p,q,extra})
        with patch.object(self.g,'changes',side_effect=AssertionError('expected manifest cache hit')):
            self.assertEqual(recent_files(self.db,self.g),manifest)
        (self.repo/p).unlink();b=self.commit('drivers: i2c: omap: remove source')
        collect(self.db,self.g,b,now,72)
        manifest=recent_files(self.db,self.g)
        self.assertEqual(manifest[b],[dict(path=p,revision=a,status='D',old_path=None)])
        collect(self.db,self.g,b,now+dt.timedelta(days=4),72)
        self.assertEqual(recent_files(self.db,self.g),{})
