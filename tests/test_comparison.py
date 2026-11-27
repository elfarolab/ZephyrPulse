import datetime as dt
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_pulse
from pulse import UTC, collect, render
from intelligence import inventory, release_tags, update_history, render_extra
from comparison import canonical, release_snapshots

class ComparisonTest(unittest.TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit

    def test_exact_target_snapshots_and_global_news(self):
        self.put(self.board+'board.yml','board:\n  name: kit\n  socs:\n    - name: chip\n')
        self.put(self.board+'kit.yaml','identifier: kit/chip/cpu0\narch: arm\nram: 256\nflash: 1024\nsupported: [can, usb_device, eth]\n')
        self.put(self.board+'kit_cpu1.yaml','identifier: kit/chip/cpu1\nsupported: [gpio]\n')
        old=self.commit('initial board support'); self.git('tag','v3.7.1',old)
        self.put(self.board+'kit.yaml','identifier: kit/chip/cpu0\narch: arm\nram: 256\nflash: 1024\nsupported: [can, canfd, usb_device, eth]\n')
        stable=self.commit('add CAN FD'); self.git('tag','v4.0.0',stable)
        self.put(self.board+'kit_cpu1.yaml','identifier: kit/chip/cpu1\nsupported: [gpio, adc]\n')
        self.put('boards/other/unwatched/board.yml','board:\n  name: unwatched\n  socs:\n    - name: chip2\n')
        head=self.commit('add ADC and unwatched board');now=dt.datetime.now(UTC)
        collect(self.db,self.g,head,now,72);boards=inventory(self.g,head)
        cov=update_history(self.db,self.g,head,now,boards,90,0)
        tags=release_tags(self.g,{'3.7'}); snaps=release_snapshots(self.g,tags,boards,{},now)
        self.assertEqual([x['tag'] for x in snaps],['v4.0.0','v3.7.1'])
        docs=self.root/'docs';render(self.db,docs,now,72,'https://example.invalid/',boards=boards)
        render_extra(self.db,docs,now,head,boards,cov,tags,{'status':'disabled','items':[]},{},{'boards':['*mcxn*']},'https://example.invalid/',preferences={'requirements':['can-fd']},snapshots=snaps)
        data=json.loads((docs/'intelligence.json').read_text());targets={t['target']:t for t in data['comparison']['targets']}
        a=targets['kit/chip/cpu0'];b=targets['kit/chip/cpu1'];unknown=targets['unwatched/chip2']
        self.assertIn('can-fd',a['metadata']['features']);self.assertNotIn('can-fd',a['releases'][1]['features'])
        self.assertNotIn('can',b['metadata']['features']);self.assertIn('adc',b['metadata']['features']);self.assertNotIn('adc',b['releases'][0]['features'])
        self.assertIsNone(unknown['metadata']);self.assertFalse(unknown['releases'][0]['found'])
        self.assertEqual(a['metadata']['ram'],256);self.assertEqual(a['metadata']['flash'],1024)
        self.assertEqual(data['preferences']['requirements'],['can-fd']);self.assertIn('unwatched',(docs/'board.md').read_text()); self.assertNotIn('pulse-category-summary',(docs/'index.md').read_text()); self.assertIn('Watchlist highlights',(docs/'index.md').read_text())
        self.assertTrue((docs/'compare.md').exists());self.assertTrue((docs/'settings.md').exists())

    def test_compact_explorer_headers_preserve_coverage(self):
        now=dt.datetime.now(UTC); head=self.base; docs=self.root/'docs'
        collect(self.db,self.g,head,now,72); boards=inventory(self.g,head)
        cov={'processed':6504,'total':11193,'days':90,'complete':False,'classification_pending':4988}
        render(self.db,docs,now,72,'https://example.invalid/',boards=boards)
        render_extra(self.db,docs,now,head,boards,cov,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/')
        for page, marker in [('boards.md','pulse-board-filter'),('vendors.md','pulse-vendor-filter')]:
            body=(docs/page).read_text()
            self.assertIn(f'Updated **{now:%Y-%m-%d %H:%M UTC}**',body)
            self.assertIn(marker,body)
            for prose in ('History:', 'Backfill in progress', 'Classifier refresh pending', 'All discovered', 'Compare hardware targets'):
                self.assertNotIn(prose,body)
        self.assertEqual(json.loads((docs/'data/activity.json').read_text())['coverage'],cov)
        self.assertNotIn('Global history coverage',next((docs/'boards').glob('*.md')).read_text())
        self.assertNotIn('Hardware-focused news from upstream Zephyr.',(docs/'index.md').read_text())
        self.assertNotIn('Declared capabilities, explicit source changes',(docs/'board_feature.md').read_text())

    def test_conservative_aliases(self):
        self.assertEqual(canonical('canfd'),'can-fd');self.assertEqual(canonical('can'),'can')
        self.assertEqual(canonical('usb_host'),'usb-host');self.assertEqual(canonical('usb_device'),'usb-device')
        self.assertNotEqual(canonical('ble'),canonical('bt'))
