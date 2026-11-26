import datetime as dt
import json
from pathlib import Path
import unittest
import test_pulse
from pulse import UTC, collect, render
from intelligence import inventory, release_tags, update_history, render_extra
from comparison import release_snapshots

class EvidenceTest(unittest.TestCase):
    setUp=test_pulse.PulseTest.setUp
    git=test_pulse.PulseTest.git
    put=test_pulse.PulseTest.put
    commit=test_pulse.PulseTest.commit

    def test_exact_target_can_fd_and_release_isolation(self):
        # Synthetic graph shaped like FRDM-MCXN947: CAN YAML only, FD SoC
        # compatible, one board target enabling a controller, another disabling it.
        self.put(self.board+'kit.yaml','identifier: kit/chip/cpu0\narch: arm\nsupported: [can]\n')
        self.put(self.board+'kit_cpu1.yaml','identifier: kit/chip/cpu1\narch: arm\nsupported: [gpio]\n')
        self.put(self.board+'kit_chip_cpu0.dts','#include <acme/chip.dtsi>\n#include "cpu0.dtsi"\n')
        self.put(self.board+'kit_chip_cpu1.dts','#include <acme/chip.dtsi>\n')
        self.put(self.board+'cpu0.dtsi','&flexcan0 { status = "disabled"; };\n')
        self.put('dts/arm/acme/chip.dtsi','#include "common.dtsi"\n')
        self.put('dts/arm/acme/common.dtsi','/ { flexcan0: can@1 { compatible = "nxp,flexcan-fd", "nxp,flexcan"; status = "disabled"; }; flexcan1: can@2 { compatible = "nxp,flexcan-fd"; status = "disabled"; }; crypto@3 { compatible = "nxp,els"; }; };')
        self.put('dts/bindings/can/nxp,flexcan-fd.yaml','compatible: "nxp,flexcan-fd"\n')
        self.put('drivers/can/flexcan.c','#define DT_DRV_COMPAT nxp_flexcan\n')
        old=self.commit('disabled CAN controller');self.git('tag','v4.0.0',old)
        self.put(self.board+'cpu0.dtsi','&flexcan0 { status = "okay"; };\n')
        head=self.commit('enable board CAN FD controller');now=dt.datetime.now(UTC)
        boards=inventory(self.g,head); b=next(iter(boards.values()))
        a=b['metadata']['kit/chip/cpu0']['dts_evidence']; c=b['metadata']['kit/chip/cpu1']['dts_evidence']
        self.assertIn('can-fd',a['features']);self.assertIn('crypto',a['features']);self.assertNotIn('can-fd',c['features']);self.assertIn('can-fd',c['present_features'])
        self.assertNotIn('kit/chip',b['targets']);self.assertNotIn('can-fd',b['metadata']['kit/chip/cpu0']['features'])
        node=next(n for n in a['nodes'] if n['node']=='&flexcan0' and n['compatible']=='nxp,flexcan-fd')
        self.assertTrue(node['positive']);self.assertIn('drivers/can/flexcan.c',node['driver_paths']);self.assertIn(self.board+'cpu0.dtsi',node['status_paths'])
        self.assertFalse(next(n for n in a['nodes'] if n['node']=='&flexcan1')['positive'])
        collect(self.db,self.g,head,now,72);cov=update_history(self.db,self.g,head,now,boards,90,0)
        tags=release_tags(self.g,set());snaps=release_snapshots(self.g,tags,boards,{},now)
        docs=self.root/'docs';render(self.db,docs,now,72,'https://example.invalid/',boards=boards)
        render_extra(self.db,docs,now,head,boards,cov,tags,{'status':'disabled','items':[]},{},{},'https://example.invalid/',snapshots=snaps)
        data=json.loads((docs/'intelligence.json').read_text());targets={t['target']:t for t in data['comparison']['targets']}
        m=targets['kit/chip/cpu0'];self.assertIn('can-fd',m['metadata']['source_features']);self.assertNotIn('can-fd',m['releases'][0]['source_features'])
        boardpage=(docs/'boards'/f"{b['slug']}.md").read_text();self.assertIn('nxp,flexcan-fd',boardpage);self.assertIn('DTS source hint',boardpage);self.assertIn('/commits/'+head,boardpage)
        self.assertIn('hide:\n  - toc',(docs/'index.md').read_text())

    def test_home_and_category_complete(self):
        for i in range(18): self.put(f'boards/acme/new{i}/board.yml',f'board:\n  name: new{i}\n  socs:\n    - name: chip\n')
        head=self.commit('many new boards');now=dt.datetime.now(UTC);collect(self.db,self.g,head,now,72)
        docs=self.root/'docs';render(self.db,docs,now,72,'https://example.invalid/')
        home=(docs/'index.md').read_text();category=(docs/'board.md').read_text()
        self.assertEqual(home.count('class="pulse-news-row pulse-cat-board"'),19)
        self.assertEqual(category.count('class="pulse-news-row pulse-cat-board"'),19)
        self.assertIn('data-pulse-news="100"',category)
        self.assertIn('hide:\n  - toc',home)
