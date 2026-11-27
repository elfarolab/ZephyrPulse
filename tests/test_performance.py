"""Regression tests for incremental analysis and byte-stable board content."""
import datetime as dt
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import test_pulse
from pulse import UTC, collect, render
from intelligence import inventory, release_tags, render_extra
from comparison import release_snapshots
from generators.base import content_changes, build_site
from test_generators import Fake


class PerformanceTests(TestCase):
    setUp = test_pulse.PulseTest.setUp
    git = test_pulse.PulseTest.git
    put = test_pulse.PulseTest.put
    commit = test_pulse.PulseTest.commit

    def setup_boards(self):
        self.put(self.board+'kit.yaml','identifier: kit/chip\narch: arm\nsupported: [gpio]\n')
        self.put(self.board+'kit_chip.dts','#include <acme/chip.dtsi>\n#include "optional.dtsi"\n')
        self.put('dts/arm/acme/chip.dtsi','/ { flexcan0: can@1 { compatible = "nxp,flexcan-fd"; status = "disabled"; }; other0: adc@2 { compatible = "acme,adc"; status = "okay"; }; };')
        self.put('boards/acme/second/board.yml','board:\n  name: second\n  socs:\n    - name: chip2\n')
        self.put('boards/acme/second/second.yaml','identifier: second/chip2\narch: arm\nsupported: [gpio]\n')
        self.put('boards/acme/second/second_chip2.dts','/ { i2c0: i2c@0 { compatible = "acme,i2c"; }; };')
        return self.commit('add distinct target evidence')

    def get(self, boards, name):
        return next(b for b in boards.values() if b['name']==name)

    def ev(self, board):
        return next(iter(board['metadata'].values()))['dts_evidence']

    def test_inventory_cache_full_and_selective_hits(self):
        head=self.setup_boards(); first=inventory(self.g,head,self.db)
        self.put('doc/unrelated.rst','unrelated'); next_head=self.commit('documentation only')
        with patch('intelligence._inventory',side_effect=AssertionError('full cache should hit')):
            self.assertEqual(inventory(self.g,next_head,self.db),first)
        self.put('drivers/can/flexcan.c','#define DT_DRV_COMPAT nxp_flexcan_fd\n')
        changed=self.commit('add CAN driver')
        with self.assertLogs(level='INFO') as logs:
            boards=inventory(self.g,changed,self.db)
        self.assertIn('Target evidence cache: 1 hits, 1 computed','\n'.join(logs.output))
        self.assertEqual(self.get(boards,'second'),self.get(first,'second'))
        self.assertEqual(self.get(boards,'kit')['evidence_revision'],changed)
        self.assertIn('drivers/can/flexcan.c',self.ev(self.get(boards,'kit'))['nodes'][0]['driver_paths'])
        self.assertEqual(inventory(self.g,changed,self.db),boards)

    def test_binding_and_previously_missing_include_invalidate(self):
        head=self.setup_boards(); first=inventory(self.g,head,self.db)
        self.assertNotIn('adc',self.ev(self.get(first,'kit'))['features'])
        self.put('dts/bindings/adc/acme,adc.yaml','compatible: "acme,adc"\n'); new=self.commit('add binding')
        boards=inventory(self.g,new,self.db)
        self.assertIn('adc',self.ev(self.get(boards,'kit'))['features'])
        self.assertEqual(self.get(first,'second'),self.get(boards,'second'))
        self.put(self.board+'optional.dtsi','&flexcan0 { status = "okay"; };'); new=self.commit('enable CAN FD by formerly missing include')
        next_boards=inventory(self.g,new,self.db)
        self.assertIn('can-fd',self.ev(self.get(next_boards,'kit'))['features'])
        self.assertEqual(self.get(first,'second'),self.get(next_boards,'second'))
        self.git('rm',self.board+'optional.dtsi'); new=self.commit('remove optional include')
        self.assertNotIn('can-fd',self.ev(self.get(inventory(self.g,new,self.db),'kit'))['features'])

    def test_revision_anchor_resets_after_rewrite(self):
        head=self.setup_boards(); inventory(self.g,head,self.db)
        self.git('reset','--hard',self.base)
        self.put('doc/rewrite.rst','rewrite'); new=self.commit('new branch history')
        b=inventory(self.g,new,self.db)
        self.assertEqual(len(b),1)
        self.assertEqual(self.get(b,'kit')['evidence_revision'],new)

    def test_release_cache_retag_new_paths_and_live_policy(self):
        head=self.setup_boards(); self.git('tag','v4.0.0',head)
        boards=inventory(self.g,head,self.db); now=dt.datetime.now(UTC)
        policy={'series':{'4.0':{'eol':now.date().isoformat(),'status':'Supported'}}}
        tags=release_tags(self.g,{'4.0'})
        a=release_snapshots(self.g,tags,boards,policy,now,self.db)
        with patch('intelligence.blobs',side_effect=AssertionError('release cache should hit')):
            b=release_snapshots(self.g,tags,boards,policy,now+dt.timedelta(days=1),self.db)
        self.assertEqual(a[0]['paths'],b[0]['paths'])
        self.assertEqual(b[0]['lifecycle'],'End of life per configured policy')
        self.put(self.board+'alternate.yaml','identifier: kit/chip/alternate\nsupported: [spi]\n'); newer=self.commit('new target')
        boards=inventory(self.g,newer,self.db)
        b=release_snapshots(self.g,tags,boards,policy,now,self.db)
        self.assertNotIn(self.board+'alternate.yaml',b[0]['paths'])
        # A missing path is cached too; moving a tag invalidates that cache.
        with patch('intelligence.blobs',side_effect=AssertionError('cached absence should hit')):
            release_snapshots(self.g,tags,boards,policy,now,self.db)
        self.git('tag','-f','v4.0.0',newer)
        b=release_snapshots(self.g,release_tags(self.g,{'4.0'}),boards,policy,now,self.db)
        self.assertIn(self.board+'alternate.yaml',b[0]['paths'])

    def test_board_markdown_stability_and_html_diffs(self):
        head=self.setup_boards(); now=dt.datetime.now(UTC); docs=self.root/'docs'
        def cycle(head, now, processed):
            boards=inventory(self.g,head,self.db)
            collect(self.db,self.g,head,now,72)
            render(self.db,docs,now,72,'https://example.invalid/',boards=boards)
            cov={'processed':processed,'total':processed+1,'days':90,'complete':False}
            render_extra(self.db,docs,now,head,boards,cov,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/')
            return boards
        boards=cycle(head,now,1)
        files={b['name']:docs/'boards'/f"{b['slug']}.md" for b in boards.values()}
        before={k:p.read_bytes() for k,p in files.items()}; times={k:p.stat().st_mtime_ns for k,p in files.items()}
        # The test renderer is intentionally not Zensical: check byte diff contract.
        build_site(self.root,Fake(),'https://example.invalid/')
        self.put('doc/another.rst','unrelated'); new=self.commit('unrelated doc')
        cycle(new,now+dt.timedelta(hours=4),5)
        for k,p in files.items():
            self.assertEqual(before[k],p.read_bytes()); self.assertEqual(times[k],p.stat().st_mtime_ns)
        with self.assertLogs(level='INFO') as logs: build_site(self.root,Fake(),'https://example.invalid/')
        self.assertIn('Board HTML: 0 new, 0 changed, 2 unchanged, 0 removed','\n'.join(logs.output))
        self.put(self.board+'kit.yaml','identifier: kit/chip\narch: arm\nsupported: [gpio, can]\n'); new=self.commit('change board metadata')
        cycle(new,now+dt.timedelta(hours=8),7)
        self.assertNotEqual(before['kit'],files['kit'].read_bytes()); self.assertEqual(before['second'],files['second'].read_bytes())
        self.assertIn(new,files['kit'].read_text())
        with self.assertLogs(level='INFO') as logs: build_site(self.root,Fake(),'https://example.invalid/')
        self.assertIn('Board HTML: 0 new, 1 changed, 1 unchanged, 0 removed','\n'.join(logs.output))
        # A board removal must not leave stale HTML in output.
        self.git('rm','-r','boards/acme/second'); new=self.commit('remove board')
        cycle(new,now+dt.timedelta(hours=12),8)
        self.assertFalse(files['second'].exists())
        with self.assertLogs(level='INFO') as logs: build_site(self.root,Fake(),'https://example.invalid/')
        self.assertIn('Board HTML: 0 new, 0 changed, 1 unchanged, 1 removed','\n'.join(logs.output))

    def test_scoped_upgrade_reuses_actual_cached_producers(self):
        from performance import _LEGACY_VERSION, _LEGACY_BASELINE, _versions
        from news_groups import recent_files
        if _versions() != _LEGACY_BASELINE:
            self.skipTest('Exact v0.3.30 producer migration only applies to unchanged baseline')
        head=self.setup_boards(); self.git('tag','v4.0.0',head)
        now=dt.datetime.now(UTC)
        boards=inventory(self.g,head,self.db)
        tags=release_tags(self.g,{'4.0'})
        snapshots=release_snapshots(self.g,tags,boards,{},now,self.db)
        collect(self.db,self.g,head,now,72)
        manifests=recent_files(self.db,self.g)
        self.db.execute('UPDATE performance_cache SET version=?',(_LEGACY_VERSION,));self.db.commit()
        with patch('intelligence._inventory',side_effect=AssertionError('inventory recomputed')), \
             patch('intelligence.blobs',side_effect=AssertionError('release snapshot recomputed')), \
             patch.object(self.g,'changes',side_effect=AssertionError('Git manifest recomputed')), \
             self.assertLogs(level='INFO') as logs:
            self.assertEqual(inventory(self.g,head,self.db),boards)
            self.assertEqual(release_snapshots(self.g,tags,boards,{},now,self.db),snapshots)
            self.assertEqual(recent_files(self.db,self.g),manifests)
        self.assertEqual(sum('migrated to scoped fingerprint' in x for x in logs.output),3)
