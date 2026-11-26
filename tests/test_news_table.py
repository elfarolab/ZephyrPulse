from html.parser import HTMLParser
from unittest import TestCase
from news_table import render_news_table
class NewsTests(TestCase):
    def test_evidence_escaped_and_preserved(self):
        e={'sha':'a'*40,'kind':'dts','subject':'<script>bad</script>','commit_subject':'& "hello"','detail':'<img onerror=bad>','path':'dts/a b.dtsi','committed':'2026-11-26T17:00:00+00:00','confidence':'candidate'}
        html=render_news_table([e]*205,{'a'*40:{'status':'main_only'}})
        self.assertEqual(html.count('class="pulse-news-row '),205);self.assertEqual(html.count('class="pulse-news-detail"'),205)
        self.assertNotIn('<script>',html);self.assertNotIn('<img onerror',html);self.assertIn('&lt;script&gt;',html);self.assertIn('dts/a%20b.dtsi',html);self.assertIn('Main only',html);self.assertIn('colspan="8"',html)
        self.assertIn('No matching events',render_news_table([]))
