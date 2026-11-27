"""Exercise rolling freshness on real static/dynamic news and timeline markup."""
import datetime as dt
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_grouped_news, render_board_timeline


def main():
    now=dt.datetime(2026,11,27,15,0,tzinfo=dt.timezone.utc)
    ages=[0,3.99,4,11.99,12,23.99,24,-1]
    records=[dict(sha=f'{i:040x}',kind='driver',subject=f'Driver {i}',commit_subject=f'Driver change uniqueitem{i}xyz',detail='evidence',path=f'drivers/i2c/i2c_test{i}.c',committed=(now-dt.timedelta(hours=age)).isoformat(),confidence='observed') for i,age in enumerate(ages)]
    history=[dict(records[0],label='New driver'),dict(records[6],label='Old driver')]
    html=render_grouped_news(records,'driver')+render_board_timeline(history,{},lambda s:'Unknown')
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'):args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.clock.install(time=now)
        page.set_content('<html><body data-md-color-scheme="default"><main class="md-content">'+html+'<div id="dynamic"></div><table><tbody><tr id="inventory"><td>Undated board</td></tr></tbody></table></main></body></html>')
        for name in ['pulse.css']:
            page.add_style_tag(path=ROOT/'docs/assets'/name)
        for name in ['theme-zensical.js','table-controls.js','news.js']:
            page.add_script_tag(path=ROOT/'docs/assets'/name)
        # Freeze at the exact boundary to avoid test timing drift.
        page.evaluate('now=>PulseFreshness.scan(document,now)',now.timestamp()*1000)
        for selector,n in [('.pulse-news-row.pulse-fresh-last',2),('.pulse-news-row.pulse-fresh-recent',2),('.pulse-news-row.pulse-fresh-today',2),('.pulse-news-row .pulse-fresh-badge',2),('.pulse-board-timeline .pulse-fresh-badge',1)]:
            expect(page.locator(selector)).to_have_count(n)
        assert page.locator('#inventory').get_attribute('class') is None
        assert page.evaluate("PulseFreshness.ageBand('2026-11-27')") == ''
        assert page.evaluate("PulseFreshness.ageBand('invalid')") == ''
        row=page.locator('.pulse-news-row.pulse-fresh-last').first
        def bg():return row.locator('td').first.evaluate('el=>getComputedStyle(el).backgroundColor')
        light=bg();page.evaluate("document.body.dataset.mdColorScheme='slate'");dark=bg();assert light!=dark,(light,dark)
        for width in (1440,390):
            page.set_viewport_size({'width':width,'height':900})
            assert row.locator('.pulse-news-expand').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
            assert row.locator('.pulse-news-toggle').evaluate('el=>parseFloat(getComputedStyle(el).fontSize)>=16')
        row.locator('.pulse-news-toggle').click();expect(page.locator('.pulse-news-detail:visible')).to_have_count(1)
        page.set_viewport_size({'width':1440,'height':900})
        page.get_by_role('button',name='UTC date / time').first.click();expect(page.locator('.pulse-news-detail:visible')).to_have_count(1)
        assert page.locator('.pulse-news-row .pulse-fresh-badge').count()==2
        page.get_by_label('Filter news').fill('uniqueitem1xyz');expect(page.locator('.pulse-news-row:visible')).to_have_count(1)
        page.get_by_label('Filter news').fill('last');expect(page.locator('.pulse-news-row:visible')).to_have_count(0)
        page.get_by_label('Filter news').fill('')
        page.evaluate('records=>PulseNews.renderGrouped(document.getElementById("dynamic"),records,new Map(),"driver",{})',records)
        expect(page.locator('#dynamic .pulse-fresh-badge')).to_have_count(2)
        page.evaluate('stamp=>{const el=document.createElement("article");el.id="search-result";el.dataset.commitTime=stamp;document.body.append(el)}',records[0]['committed'])
        expect(page.locator('#search-result .pulse-fresh-badge')).to_have_count(1)
        # One originally recent row crosses the four-hour threshold after one minute.
        page.clock.fast_forward(60000)
        expect(page.locator('#dynamic .pulse-fresh-badge')).to_have_count(1)
        page.evaluate('now=>PulseFreshness.scan(document,now)',(now+dt.timedelta(hours=25)).timestamp()*1000)
        expect(page.locator('.pulse-fresh-badge')).to_have_count(0)
        expect(page.locator('.pulse-fresh-last,.pulse-fresh-recent,.pulse-fresh-today')).to_have_count(0)
        assert not errors,errors
        browser.close()
    print('Commit freshness boundaries, light/dark contrast, dynamic rows, sorting, filtering, expansion and auto-expiry passed.')

if __name__=='__main__':main()
