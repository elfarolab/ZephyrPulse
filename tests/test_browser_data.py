import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from browser_data import publish_catalog, encoded
from news_table import render_category_summary, render_news_table


class BrowserDataTests(unittest.TestCase):
    def test_split_preserves_states_and_full_evidence_and_stability(self):
        ev = {'features':['can-fd'], 'present_features':['can-fd','usb'], 'nodes':[{'compatible':'nxp,flexcan-fd','compatible_paths':['dts/a.dtsi'],'status_paths':['boards/b.dts'],'features':['can-fd'],'extra':'x'*10000}]}
        comparison = {'targets':[{'id':'kit::cpu0','board_id':'kit','metadata':{'features':['can'],'source_features':['can-fd'],'dts_evidence':ev},'releases':[{'tag':'v4.0.0','found':True,'features':['can'],'source_features':['can-fd'],'dts_evidence':ev},{'tag':'v3.7.0','found':False,'features':None,'dts_evidence':{}}]}], 'snapshots':[]}
        with tempfile.TemporaryDirectory() as tmp:
            docs=Path(tmp)
            before=encoded(comparison)
            publish_catalog(docs,copy.deepcopy(comparison),{'updated':'one'})
            c=json.loads((docs/'intelligence.json').read_text());t=c['comparison']['targets'][0]
            self.assertEqual(t['metadata']['dts_evidence'],{'present_features':['can-fd','usb']})
            self.assertEqual(t['releases'][0]['source_features'],['can-fd'])
            path=docs/t['evidence_url'];raw=path.read_bytes();self.assertEqual(path.stem,hashlib.sha256(raw).hexdigest())
            full=json.loads(raw)['targets']['kit::cpu0'];self.assertEqual(full['main'],ev);self.assertEqual(full['v4.0.0'],ev);self.assertNotIn('v3.7.0',full)
            self.assertLess((docs/'intelligence.json').stat().st_size,len(before)//10)
            self.assertTrue((docs/'data/news-view.json').is_file());self.assertNotIn('updated',json.loads((docs/'data/preferences.json').read_text()))
            stamp=path.stat().st_mtime_ns
            publish_catalog(docs,copy.deepcopy(comparison),{'updated':'two'})
            self.assertEqual(path.stat().st_mtime_ns,stamp)
            publish_catalog(docs,{'targets':[],'snapshots':[]},{})
            self.assertTrue(path.exists()) # previous snapshot remains available for cached clients
            publish_catalog(docs,{'targets':[],'snapshots':[]},{})
            self.assertFalse(path.exists())

    def test_category_summary_and_encoded_links(self):
        e=dict(sha='a'*40,kind='driver',subject='ti_ads122s14 / a&b',detail='evidence',committed='2026-11-26T17:00:00Z',confidence='observed')
        summary=render_category_summary([e]*200,{}, {}, {})
        self.assertEqual(summary.count('class="pulse-news-row '),3)
        self.assertIn('View all 200 drivers',summary)
        table=render_news_table([e]);self.assertIn('href="driver.html"',table)
        self.assertIn('driver.html?subject=ti_ads122s14%20%2F%20a%26b',table)
        self.assertNotIn('hardware-search.html?subject=ti_ads122s14%20%2F%20a%26b',table)
        grouped=render_category_summary([e,dict(e,kind='dts')],{},{},{})
        self.assertIn('dts.html?subject=ti_ads122s14%20%2F%20a%26b',grouped)
        self.assertIn('Same subject in other categories',grouped)
