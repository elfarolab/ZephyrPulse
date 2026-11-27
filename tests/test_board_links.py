from unittest import TestCase
from board_links import BoardLinks
from news_table import render_news_table


def board(name, folder, slug, targets=()):
    return dict(name=name,folder=folder,slug=slug,targets=list(targets),full_name=name)


class BoardLinkTests(TestCase):
    def setUp(self):
        self.boards={'a':board('kit','boards/acme/kit','kit-abc',['kit/chip/cpu0']),
                     'b':board('other','boards/acme/kit','other-def',['other/chip']),
                     'c':board('kit','boards/else/kit','kit-ghi',['kit/chip/cpu1'])}
        self.resolver=BoardLinks(self.boards)
    def test_exact_and_ambiguous(self):
        resolve=self.resolver.resolve
        self.assertEqual(resolve({'kind':'board','subject':'KIT/chip/cpu0'}),'a')
        self.assertEqual(resolve({'kind':'board','subject':'kit'},['a','b']),'a')
        self.assertIsNone(resolve({'kind':'board','subject':'kit'}))
        self.assertIsNone(resolve({'kind':'board_candidate','subject':'boards/acme/kit'},['a','b']))
        self.assertIsNone(resolve({'kind':'soc','subject':'kit'}))
        self.assertIsNone(resolve({'kind':'driver','subject':'other'}))
        self.assertIsNone(resolve({'kind':'board','subject':'unknown'}))
        self.assertEqual(self.resolver.proposal('boards: add kit/chip/cpu0 support'),['a'])
        self.assertEqual(self.resolver.proposal('drivers: change kit/chip/cpu0'),[])
    def test_static_primary_and_secondary_links(self):
        e=dict(sha='a'*40,kind='board_feature',subject='kit/chip/cpu0',detail='evidence',committed='2026-11-26T17:00:00Z',confidence='observed',path='boards/acme/kit/kit.yaml')
        html=render_news_table([e],boards=self.boards)
        self.assertIn('class="pulse-board-profile-link" href="boards/kit-abc.html"',html)
        self.assertIn('Subject filter: <a class="pulse-subject-filter"',html)
        self.assertIn('board_feature.html?subject=kit%2Fchip%2Fcpu0',html)
        import re
        links=re.search(r'<p class="pulse-news-links">(.*?)</p>',html).group(1)
        for glyph in ('commit','github','board','search'):
            self.assertIn('pulse-i-'+glyph,links)
        self.assertIn('pulse-i-filter',html)
        self.assertIn('href="boards/kit-abc.html" class="pulse-detail-link"',links)
        self.assertNotIn('pulse-board-profile-link',render_news_table([dict(e,subject='boards/acme/kit')],boards=self.boards))
