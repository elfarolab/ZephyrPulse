"""Portable icon assets are available for every generated category."""
from pathlib import Path
import unittest
import re
import xml.etree.ElementTree as ET
from pulse import CATEGORIES, CATEGORY_ICONS, icon

ROOT=Path(__file__).resolve().parents[1]
class IconTests(unittest.TestCase):
    def test_assets_and_category_mapping(self):
        assets=ROOT/'docs/assets'
        self.assertEqual(set(CATEGORIES),set(CATEGORY_ICONS))
        css=(assets/'pulse.css').read_text()
        for name in set(CATEGORY_ICONS.values())|{'arrow','compare','settings','search','commit','source','watch','overview','intelligence'}:
            self.assertIn(f'.pulse-i-{name}',css)
            self.assertIn(f'icons/{name}.svg',css)
            self.assertEqual(ET.parse(assets/'icons'/f'{name}.svg').getroot().tag,'{http://www.w3.org/2000/svg}svg')
            self.assertIn('aria-hidden="true"',icon(name))
        for k in CATEGORIES:
            self.assertIn(f'.pulse-cat-{k}',css)
