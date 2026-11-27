import datetime as dt
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pulse import Git, collect, connect, nodes, render, variants, board_defs, UTC

class PulseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.repo = self.root/'repo'; self.repo.mkdir()
        self.git('init','-b','main'); self.git('config','user.email','test@example.invalid'); self.git('config','user.name','Test')
        self.board='boards/acme/kit/'
        self.put(self.board+'board.yml','board:\n  name: kit\n  socs:\n    - name: chip\n')
        self.put(self.board+'kit.yaml','identifier: kit/chip\nsupported:\n  - gpio\n')
        self.put(self.board+'kit.dts','#include <acme/chip.dtsi>\n&can0 { status = "disabled"; };\n')
        self.put('dts/arm/acme/chip.dtsi','/ { sensor0: sensor@48 { compatible = "acme,temp123"; status = "okay"; }; };')
        self.put('dts/bindings/sensor/acme,temp123.yaml','compatible: "acme,temp123"\n')
        self.base=self.commit('initial board')
        self.db=connect(self.root/'db.sqlite')
        self.addCleanup(self.db.close)
        self.g=Git(self.repo)
    def git(self,*args): return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    def put(self,path,text):
        p=self.repo/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
    def commit(self,msg):
        self.git('add','.'); self.git('commit','-m',msg); return self.git('rev-parse','HEAD')
    def events(self,sha): return [dict(r) for r in self.db.execute('SELECT * FROM events WHERE sha=?',(sha,))]
    def test_collection_and_render(self):
        now=dt.datetime.now(UTC)
        collect(self.db,self.g,self.base,now,72)
        self.assertTrue(any(x['kind']=='board' for x in self.events(self.base)))
        self.put(self.board+'kit.dts','#include <acme/chip.dtsi>\n&can0 { status = "okay"; };\n')
        self.put(self.board+'kit.yaml','identifier: kit/chip\nsupported:\n  - gpio\n  - can\n')
        self.put('drivers/sensor/acme/temp123/temp123.c','#define DT_DRV_COMPAT acme_temp123\n')
        self.put('doc/new.rst','New page\n========\n')
        head=self.commit('enable CAN and introduce sensor driver')
        collect(self.db,self.g,head,now,72)
        events=self.events(head)
        self.assertTrue(any(x['kind']=='board_feature' and 'disabled → okay' in x['detail'] for x in events))
        self.assertTrue(any(x['kind']=='board_feature' and 'metadata entry: can' in x['detail'] for x in events))
        self.assertTrue(any(x['kind']=='sensor' and x['subject']=='acme_temp123' for x in events))
        self.assertTrue(any(x['kind']=='board_candidate' and x['subject']=='boards/acme/kit' and 'shared DTS' in x['detail'] for x in events))
        self.assertTrue(any(x['kind']=='docs' for x in events))
        collect(self.db,self.g,head,now,72); self.assertEqual(events,self.events(head))
        render(self.db,self.root/'docs',now,72,'https://example.invalid/')
        home=(self.root/'docs/index.md').read_text()
        self.assertIn('Other changes',home); self.assertNotIn('pulse-category-summary',home)
        self.assertIn('  - navigation', home)
        self.assertEqual(home.count('class="pulse-stat-label"'),15)
        self.assertIn('pulse-i-capability',home)
        self.assertIn('pulse-i-compare',home)
        self.assertIn('href="board_feature.html"',home)
        self.assertIn('pulse-i-commit',(self.root/'docs/board_feature.md').read_text())
        self.assertTrue(json.loads((self.root/'docs/events.json').read_text())['events'])
        collect(self.db,self.g,head,now+dt.timedelta(days=4),72)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
    def test_rewritten_history(self):
        now=dt.datetime.now(UTC)
        self.put('doc/orphan.rst','orphan'); old=self.commit('orphan')
        collect(self.db,self.g,old,now,72)
        self.git('reset','--hard',self.base)
        self.put('doc/replacement.rst','replacement'); new=self.commit('replacement')
        collect(self.db,self.g,new,now,72)
        self.assertFalse(self.events(old)); self.assertTrue(self.events(new))
    def test_merge_net_diff(self):
        now=dt.datetime.now(UTC); collect(self.db,self.g,self.base,now,72)
        self.git('checkout','-b','feature'); self.put('doc/merged.rst','new'); side=self.commit('side')
        self.git('checkout','main'); self.git('merge','--no-ff','feature','-m','merge feature'); head=self.git('rev-parse','HEAD')
        collect(self.db,self.g,head,now,72)
        self.assertTrue(any(x['kind']=='docs' for x in self.events(head))); self.assertFalse(self.events(side))
    def test_lexical_scanner(self):
        result=nodes('/* status = "okay"; */ &uart0 { status = "disabled"; }; / { abc: test@0 { compatible = "x,y", "x,z"; }; };')
        self.assertEqual(result['&uart0']['status'],('disabled',))
        self.assertEqual(result['&abc']['compatible'],('x,y','x,z'))
    def test_variant(self):
        d=board_defs('boards:\n- name: kit\n  socs:\n  - name: chip\n    variants:\n    - name: ns\n')
        self.assertIn('kit/chip/ns',variants(d))

if __name__=='__main__': unittest.main()
