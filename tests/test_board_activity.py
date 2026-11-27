"""Board profile activity is an exact Git/association view, not a title search."""
import datetime as dt
from unittest import TestCase
from news_groups import board_recent_activity, recent_files
from intelligence import inventory, render_extra, update_history
from pulse import UTC, collect, render
import test_pulse

class BoardActivityTests(TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit

    def test_board_profile_activity_and_stability(self):
        self.put(self.board+'kit.yaml','identifier: kit/chip\nsupported: [gpio, can]\n')
        self.put(self.board+'kit_alt.yaml','identifier: kit/chip/alt\nsupported: [spi]\n')
        self.put('doc/mixed.rst','also changed')
        sha=self.commit('boards: kit: add CAN and alternate target')
        self.put('doc/unrelated.rst','unrelated board name kit')
        head=self.commit('kit is mentioned but unrelated')
        now=dt.datetime.now(UTC);docs=self.root/'docs'
        def build(rev):
            collect(self.db,self.g,rev,now,72);boards=inventory(self.g,rev,self.db)
            coverage=update_history(self.db,self.g,rev,now,boards,90,0)
            files=recent_files(self.db,self.g)
            render(self.db,docs,now,72,'https://example.invalid/',boards=boards,commit_files=files)
            render_extra(self.db,docs,now,rev,boards,coverage,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/',commit_files=files)
            return docs/'boards'/next(b['slug']+'.md' for b in boards.values() if b['name']=='kit')
        page=build(head);text=page.read_text();activity=text.split('## Recent board commits')[1].split('## Target capability matrix')[0]
        self.assertEqual(activity.count('class="pulse-news-row '),2)
        self.assertIn('Affected files (3) — complete commit',activity)
        self.assertIn('doc/mixed.rst',activity);self.assertNotIn(head,activity)
        self.assertNotIn('Related hardware / news',text)
        self.assertEqual(text.count('<details class="pulse-board-target">'),2)
        self.assertIn('<summary><span>kit/chip/alt</span></summary>',text)
        self.assertLess(text.index('## Recent board commits'),text.index('## Target capability matrix'))
        for phrase in ('direct board-folder changes and classified board associations', 'No associated commits in this window', 'Exact-target YAML declarations and revision-pinned DTS source hints', 'Retained board milestones (last', 'These file-local declarations may apply'):
            self.assertNotIn(phrase,text)
        raw=text.split('## Raw board-folder devicetree evidence',1)[1]
        self.assertIn('<details class="pulse-board-target pulse-board-raw">',raw)
        self.assertIn('<th>Explicit status</th>',raw)
        self.assertIn('/blob/',raw);self.assertIn('kit.dts',raw)
        self.assertIn('&amp;can0',raw);self.assertNotIn('[source](',raw)
        self.put('doc/another.rst','unrelated');new=self.commit('another unrelated change')
        self.assertEqual(build(new).read_text(),text)
    def test_no_recent_activity_omits_empty_section(self):
        now=dt.datetime.now(UTC)+dt.timedelta(days=4);docs=self.root/'docs'
        collect(self.db,self.g,self.base,now,72);boards=inventory(self.g,self.base,self.db)
        coverage=update_history(self.db,self.g,self.base,now,boards,90,0)
        files=recent_files(self.db,self.g)
        render(self.db,docs,now,72,'https://example.invalid/',boards=boards,commit_files=files)
        render_extra(self.db,docs,now,self.base,boards,coverage,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/',commit_files=files)
        expired=next((docs/'boards').glob('*.md')).read_text()
        self.assertNotIn('## Recent board commits',expired)
        self.assertNotIn('No associated commits in this window',expired)
        self.assertIn('Choose a target from this board in comparator',expired)

    def test_direct_manifest_only_rename_shared_folder_and_boundary(self):
        boards={'a':{'folder':'boards/v/shared','name':'a'},'b':{'folder':'boards/v/shared','name':'b'},'c':{'folder':'boards/v/shared2','name':'c'}}
        sha='a'*40; other='b'*40; stamp='2026-11-27T00:00:00Z'
        commits={s:{'committed':stamp,'subject':s} for s in (sha,other)}
        manifests={sha:[dict(path='doc/new.rst',old_path='boards/v/shared/old.rst',revision=sha,status='R')],other:[dict(path='boards/v/shared2/file.c',revision=other,status='M')]}
        grouped=board_recent_activity([],commits,manifests,boards)
        self.assertEqual([r['sha'] for r in grouped['a']],[sha]);self.assertEqual([r['sha'] for r in grouped['b']],[sha]);self.assertEqual([r['sha'] for r in grouped['c']],[other])
        self.assertTrue(grouped['a'][0]['manifest_only'])
        self.assertEqual(grouped['a'][0]['change_type'],'Direct folder change')
