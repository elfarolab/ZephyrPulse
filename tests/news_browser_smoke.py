"""Exercise the portable news UI directly in Chromium, without a running website."""
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_news_table

def main():
    row=dict(sha='a'*40,kind='board',subject='test',detail='evidence',path='boards/a/kit.yaml',committed='2026-11-26T17:00:00Z',confidence='observed')
    records=[dict(row,subject=f'Item {i:03d}',kind='dts' if i%2 else 'board') for i in range(205)]
    html='<html><body><header><a class="md-header__button md-logo">Old logo</a><span class="md-header__title">Zephyr Pulse</span></header>'+render_news_table(records)+'</body></html>'
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']};exe=shutil.which('chromium')
        if exe:args['executable_path']=exe
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(html);page.add_style_tag(content=(ROOT/'docs/assets/pulse.css').read_text())
        assert page.locator('.pulse-news-detail:visible').count()==205 # no-JS fallback
        assert not page.locator('.md-header__button.md-logo').is_visible();assert page.get_by_text('Zephyr Pulse',exact=True).is_visible()
        page.add_script_tag(content=(ROOT/'docs/assets/news.js').read_text());assert page.locator('.pulse-news-row:visible').count()==100;assert page.locator('.pulse-news-detail:visible').count()==0
        first=page.locator('.pulse-news-row:visible').first;first.locator('.pulse-news-col-3').click();assert page.locator('.pulse-news-detail:visible a').count()==3;first.locator('button').press('Enter');assert page.locator('.pulse-news-detail:visible').count()==0
        first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==1;first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==100;page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==100;page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==5
        page.get_by_label('Rows per page').select_option('all');assert page.locator('.pulse-news-row:visible').count()==205
        page.get_by_label('Category',exact=True).select_option('dts');assert page.locator('.pulse-news-row:visible').count()==102
        page.get_by_label('Category',exact=True).select_option('');page.get_by_label('Filter news').fill('Item 042');assert page.locator('.pulse-news-row:visible').count()==1
        page.get_by_role('button',name='Expand page').click();assert page.locator('.pulse-news-detail:visible').count()==1;page.get_by_role('button',name='Collapse page').click();assert page.locator('.pulse-news-detail:visible').count()==0
        page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-news-row:visible').first.evaluate('el=>getComputedStyle(el).display')=='grid';assert not errors,errors
        browser.close()
    print('Direct Chromium news table test passed: logo CSS, fallback, 205 rows, expansion, pagination, filters, mobile.')
if __name__=='__main__':main()
