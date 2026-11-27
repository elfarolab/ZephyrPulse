from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from generators.asset_versions import version_assets

class AssetVersions(TestCase):
    def test_nested_refs_stability_and_changes(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'assets').mkdir(); (root/'boards').mkdir()
            js=root/'assets/news.js'; js.write_text('v1')
            css=root/'assets/pulse.css';css.write_text('css')
            rootpage=root/'index.html';nested=root/'boards/kit.html'
            rootpage.write_text('<link href="assets/pulse.css" rel="stylesheet"><script src="assets/news.js"></script><a href="assets/news.js">download</a><script src="https://example.com/assets/news.js"></script>')
            nested.write_text("<script src='../assets/news.js?test=1'></script>")
            self.assertEqual(version_assets(root),2)
            one=rootpage.read_text();two=nested.read_text()
            self.assertIn('assets/news.js?pulse_v=',one);self.assertIn('test=1&amp;pulse_v=',two)
            self.assertIn('<a href="assets/news.js">',one);self.assertIn('https://example.com/assets/news.js"',one)
            self.assertEqual(version_assets(root),0);self.assertEqual(one,rootpage.read_text())
            js.write_text('v2');self.assertEqual(version_assets(root),2)
            self.assertNotEqual(one,rootpage.read_text());self.assertNotEqual(two,nested.read_text());self.assertEqual(css.read_text(),'css')
