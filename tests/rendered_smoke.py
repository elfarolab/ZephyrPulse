"""Exercise the *actual* generated Zensical site after CI builds the Git fixture."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from playwright.sync_api import sync_playwright, expect
import re
from browser_geometry import assert_grid_rows
import shutil

ROOT=Path(__file__).resolve().parents[1]

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(ROOT/'site')))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as pw:
            args={'headless':True,'args':['--no-sandbox']}
            if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
            browser=pw.chromium.launch(**args);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_viewport_size({'width':1440,'height':900});page.goto(base+'settings.html');page.locator('.pulse-settings-card').first.wait_for();assert page.locator('.pulse-settings-card').count()==4
            fields=page.locator('.pulse-settings-card').first.locator('.pulse-setting-field')
            assert_grid_rows(fields, 2, 3)
            page.set_viewport_size({'width':390,'height':844});assert_grid_rows(fields, 1, 3)
            page.set_viewport_size({'width':1440,'height':900});page.get_by_label('Board / SoC patterns (comma separated)').fill('*kit*');page.get_by_role('button',name='Save preferences').click();page.get_by_text('Saved in this browser.').wait_for()
            page.goto(base+'compare.html');page.get_by_role('button',name='Add',exact=True).first.click();page.get_by_text('1 / 8 selected targets').wait_for()
            page.goto(base+'hardware-search.html')
            query=page.get_by_label('Find hardware or news (comma = OR)')
            kind=page.get_by_label('Result type')
            query.fill('*kit*');kind.select_option('target')
            cards=page.locator('.pulse-search-result')
            targets=cards.filter(has=page.locator('p').filter(has_text=re.compile(r'^Exact board targets(?: ·|$)')))
            target_link=targets.locator('h3').get_by_role('link',name='kit/chip',exact=True)
            # Search redraw is debounced. A news card can have the same title as
            # the exact target until the selected filter has actually been applied.
            expect(cards).to_have_count(1);expect(target_link).to_be_visible()
            page.reload();expect(query).to_have_value('*kit*');expect(kind).to_have_value('target')
            expect(cards).to_have_count(1);expect(target_link).to_be_visible()
            expect(targets.locator('.pulse-search-board-photo')).to_be_visible();target_link.click();page.get_by_role('heading',name='Target capability matrix',exact=True,level=2).wait_for();photo=page.locator('.pulse-board-photo img');photo.wait_for();photo.scroll_into_view_if_needed();page.wait_for_function("document.querySelector('.pulse-board-photo img').naturalWidth > 0");assert not errors,errors
            page.locator('.pulse-board-overview-links a .pulse-i-github').first.wait_for()
            expect(page.locator('.pulse-board-overview-links a').first).to_have_attribute('target','_blank')
            home=page.get_by_role('link',name='Zephyr Pulse home');expect(home).to_have_attribute('href',base+'index.html')
            expect(page.get_by_role('heading',name='Recent board commits',exact=True,level=2)).to_be_visible()
            expect(page.locator('.pulse-board-target')).to_have_count(1)
            target=page.locator('.pulse-board-target');assert target.get_attribute('open') is None
            target.locator(':scope > summary').click();expect(target.locator('table').first).to_be_visible()
            target.locator(':scope > summary').click();assert target.get_attribute('open') is None
            activity=page.locator('.pulse-grouped-news');expect(activity.locator('.pulse-news-row')).to_have_count(1)
            activity.locator('.pulse-news-col-6 button').click();expect(activity.locator('.pulse-news-detail:visible .pulse-affected-files > li')).to_have_count(3)
            expect(activity.get_by_role('link',name='View upstream commit')).to_have_attribute('target','_blank')
            assert page.get_by_role('link',name='Related hardware / news',exact=True).count()==0
            assert page.locator('script[src*="assets/theme-zensical.js?pulse_v="]').count()==1
            assert page.locator('link[href*="assets/pulse.css?pulse_v="]').count()==1
            page.evaluate('window.scrollTo(0,0)');home.click();page.wait_for_url(base+'index.html');page.set_viewport_size({'width':1440,'height':900});page.locator('.md-tabs').wait_for(state='visible');page.evaluate('window.scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();assert not page.locator('.md-sidebar--secondary').count() or not page.locator('.md-sidebar--secondary').is_visible();page.locator('#pulse-home-watch').get_by_text('Your browser watchlist').wait_for();assert page.get_by_role('link',name='Hardware search',exact=True).count()>0
            assert page.locator('.pulse-stats .pulse-stat-symbol .pulse-icon').count()==15
            assert page.locator('.pulse-tools a .pulse-icon').count()==4
            assert page.locator('.md-tabs__link .pulse-icon').count()==6
            assert not page.locator('.md-sidebar--primary').count() or not page.locator('.md-sidebar--primary').is_visible()
            assert page.locator('.pulse-stats .pulse-icon').first.evaluate("el=>getComputedStyle(el).maskImage!=='none'")
            assert page.locator('.md-header__button.md-logo:visible').count()==0
            assert page.locator('.pulse-category-summary').count()==0
            assert_grid_rows(page.locator('.pulse-stats a'), 5, 15)
            for category in ('dt_bindings','subsys','samples','tests','manifest','kernel','other'):
                page.locator(f'.pulse-stats a[href="{category}.html"]').click();page.wait_for_url(base+category+'.html')
                brand=page.get_by_role('link',name='Zephyr Pulse home');expect(brand).to_be_visible()
                if category!='other': expect(page.locator('.pulse-news-row:visible')).to_have_count(1)
                page.evaluate("document.querySelector('main').style.minHeight='250vh';window.scrollTo(0,document.body.scrollHeight)")
                page.wait_for_function("window.scrollY > 0")
                expect(brand).to_be_visible();expect(brand).to_have_text('Zephyr Pulse')
                assert brand.evaluate("el=>getComputedStyle(el.closest('.md-header__topic')).opacity")=='1'
                brand.click();page.wait_for_url(base+'index.html')

            page.set_viewport_size({'width':390,'height':844});assert_grid_rows(page.locator('.pulse-stats a'), 2, 15)
            page.set_viewport_size({'width':1920,'height':1000});assert page.locator('.md-main__inner').evaluate('el=>el.getBoundingClientRect().width') <= 1920*.72
            page.get_by_role('button',name='Search hardware and news').click();page.get_by_role('searchbox',name='Universal search query').fill('kit');page.locator('.pulse-universal-dialog a').filter(has_text=re.compile(r'^kit/chip$')).locator("xpath=self::a[preceding-sibling::h3[1][starts-with(normalize-space(.), 'Board targets (')]]").wait_for();page.keyboard.press('Escape');assert not page.locator('.pulse-universal-dialog').is_visible()
            page.goto(base+'board.html');page.locator('.pulse-news-row').first.wait_for();assert page.locator('.pulse-news-detail:visible').count()==0
            profile=page.locator('.pulse-news-row .pulse-board-profile-link').first;profile.wait_for();profile.click();page.wait_for_url('**/boards/*.html');page.get_by_role('heading',name='Target capability matrix',exact=True,level=2).wait_for();page.go_back();page.locator('.pulse-news-row').first.wait_for()
            page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-news-row').first.evaluate("el=>getComputedStyle(el).display")=='table-row'
            page.set_viewport_size({'width':1440,'height':900});page.goto(base+'driver.html')
            rows=page.locator('.pulse-news-row:visible');expect(rows).to_have_count(1)
            expect(rows.first.locator('.pulse-news-col-3')).to_contain_text('drivers: i2c: omap: add fixture support')
            expect(rows.first.locator('.pulse-news-col-4')).to_have_text('3')
            rows.first.locator('.pulse-news-col-6 button').click()
            expect(page.locator('.pulse-news-detail:visible .pulse-affected-files > li')).to_have_count(3)
            expect(page.locator('.pulse-news-detail:visible').get_by_role('link',name='doc/driver-note.rst')).to_be_visible()
            page.goto(base+'boards.html');groups=page.locator('.pulse-vendor-group:visible');expect(groups).to_have_count(1)
            expect(page.locator('.pulse-vendor-detail:visible')).to_have_count(0)
            groups.first.locator('.pulse-news-toggle').click();expect(page.locator('.pulse-vendor-boards tbody tr:visible')).to_have_count(1)
            expect(page.locator('.pulse-vendor-boards').get_by_role('link',name='kit',exact=True)).to_be_visible()
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
    print('Rendered Zensical site smoke test passed.')
if __name__=='__main__':main()
