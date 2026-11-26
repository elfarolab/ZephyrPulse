"""Text-only branding; old copied logo must not be used by new builds."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import tomllib
from pulse import remove_legacy_logo
from generators import get_generator
ROOT=Path(__file__).resolve().parents[1]
class UiPolishTests(TestCase):
    def test_text_only_branding(self):
        with TemporaryDirectory() as tmp:
            work=Path(tmp); docs=work/'docs'; asset=docs/'assets'/'zephyr-upstream.svg';asset.parent.mkdir(parents=True);asset.write_text('<svg/>')
            remove_legacy_logo(docs);self.assertFalse(asset.exists());remove_legacy_logo(docs)
            with patch('generators.zensical.subprocess.run'):
                get_generator({}).render(ROOT,work,'https://example.invalid/')
                theme=tomllib.loads((work/'zensical.toml').read_text())['project']['theme'];self.assertNotIn('logo',theme);self.assertNotIn('logo',theme.get('icon',{}))
            css=(ROOT/'docs/assets/pulse.css').read_text();self.assertIn('.md-header__button.md-logo,.md-nav__button.md-logo {display:none!important;}',css)
