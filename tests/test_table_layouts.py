"""Category layouts preserve scope, evidence and stable logical column IDs."""
from unittest import TestCase
from news_groups import GROUPED, group_events, group_unit
from news_table import news_columns, render_grouped_news, render_board_timeline
from test_news_groups import event


class TableLayoutTests(TestCase):
    def test_category_columns(self):
        expected = {
            'driver':[0,1,2,3,4,5,6], 'sensor':[0,2,3,4,5,6],
            'soc':[0,2,3,4,5,6], 'board':[0,2,3,4,5,6],
            'board_candidate':[0,2,3,4,5,6], 'board_change':[0,2,3,4,5,6],
            'board_feature':[0,2,3,4,5,6], 'dts':[0,3,4,5,6],
            'docs':[0,3,4,5,6], 'other':[0,3,4,5,6],
            'all':[0,1,3,4,5,6], 'release_news':[0,1,3,4,5,6],
        }
        self.assertEqual(GROUPED, set(expected)-{'all','release_news'})
        for category, ids in expected.items():
            with self.subTest(category=category):
                self.assertEqual([i for i,_ in news_columns(category,True)],ids)
                kind=category if category in GROUPED else 'driver'
                html=render_grouped_news([event(kind=kind)],category)
                self.assertIn(f'colspan="{len(ids)+1}"',html)
                self.assertEqual(html.count('data-news-column='),len(ids))
                self.assertIn('data-news-column="4">Files',html)
                if category not in {'all','release_news','driver'}:
                    self.assertNotIn('data-news-column="1"',html)
        self.assertEqual(dict(news_columns('soc',True))[2],'SoC / family')

    def test_board_identity_and_distinct_signals(self):
        a=event(kind='board',subject='kit',path='boards/a/kit/board.yml')
        b=dict(a,subject='kit2')
        c=dict(a,path='boards/b/kit/board.yml')
        self.assertEqual(len(group_events([a,b,c,dict(a,path='boards/a/kit/other.yml')],'board')),3)
        a=dict(a,kind='board_feature',detail='New supported metadata entry: can')
        b=dict(a,detail='New supported metadata entry: spi')
        c=dict(a,path='boards/a/kit/other.yml')
        rows=[a,b,c]
        self.assertEqual(len(group_events(rows,'board_feature')),2)
        self.assertEqual(group_unit('board_feature'),'capability signals')
        html=render_grouped_news(rows,'board_feature')
        self.assertIn('New supported metadata entry: can',html)
        self.assertIn('New supported metadata entry: spi',html)
        self.assertEqual(html.count('class="pulse-signal-preview"'),2)
        self.assertEqual(html.count('class="pulse-news-row '),2)

    def test_mixed_groups_preserve_categories_and_release_metadata(self):
        a=event(); b=event(kind='docs',path='doc/driver.rst')
        status={'first_release':'v4.0.0','latest_release':'v4.5.0','lts_tags':['v3.7.9']}
        html=render_grouped_news([a,b],'all',{a['sha']:status})
        self.assertEqual(html.count('class="pulse-news-row '),1)
        self.assertIn('data-news-column="1">Category',html)
        self.assertIn('Drivers ·',html); self.assertIn('Documentation ·',html)
        self.assertIn('Latest tracked containing tag: v4.5.0',html)
        self.assertIn('LTS tags: v3.7.9',html)
        self.assertIn('doc/driver.rst',html)

    def test_board_timeline_groups_only_equal_commits(self):
        a=dict(sha='a'*40,committed='2026-11-27T02:26:00Z',label='CAN',confidence='observed',path='boards/a/kit/a.dts')
        b=dict(a,label='SPI',confidence='candidate',path='boards/a/kit/b.dts')
        c=dict(a,sha='b'*40,label='<unsafe>')
        html=render_board_timeline([a,b,c],{},lambda s:'Unknown')
        self.assertEqual(html.count('<tr><td>'),2)
        self.assertIn('2 milestones',html); self.assertIn('SPI (candidate)',html)
        self.assertIn('a.dts',html); self.assertIn('b.dts',html)
        self.assertNotIn('<unsafe>',html)
        self.assertIn('&lt;unsafe&gt;',html)
        self.assertIn('No retained milestone',render_board_timeline([],{},str))
