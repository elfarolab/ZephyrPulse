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
            expect(targets.locator('.pulse-search-board-photo')).to_be_visible();target_link.click();page.get_by_text('Target capability matrix',exact=True).wait_for();photo=page.locator('.pulse-board-photo img');photo.wait_for();photo.scroll_into_view_if_needed();page.wait_for_function("document.querySelector('.pulse-board-photo img').naturalWidth > 0");assert not errors,errors
            page.locator('.pulse-board-overview-links a .pulse-i-github').first.wait_for()
            assert page.locator('script[src*="assets/theme-zensical.js?pulse_v="]').count()==1
            assert page.locator('link[href*="assets/pulse.css?pulse_v="]').count()==1
            page.goto(base+'index.html');page.set_viewport_size({'width':1440,'height':900});page.locator('.md-tabs').wait_for(state='visible');page.evaluate('window.scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();assert not page.locator('.md-sidebar--secondary').count() or not page.locator('.md-sidebar--secondary').is_visible();page.locator('#pulse-home-watch').get_by_text('Your browser watchlist').wait_for();assert page.get_by_role('link',name='Hardware search',exact=True).count()>0
            assert page.locator('.pulse-stats .pulse-stat-symbol .pulse-icon').count()==10
            assert page.locator('.pulse-tools a .pulse-icon').count()==4
            assert page.locator('.md-tabs__link .pulse-icon').count()==6
            assert not page.locator('.md-sidebar--primary').count() or not page.locator('.md-sidebar--primary').is_visible()
            assert page.locator('.pulse-stats .pulse-icon').first.evaluate("el=>getComputedStyle(el).maskImage!=='none'")
            assert page.locator('.md-header__button.md-logo:visible').count()==0
            assert page.locator('.pulse-category-summary').count()==0
            assert_grid_rows(page.locator('.pulse-stats a'), 5, 10)
            page.locator('.pulse-stats a[href="other.html"]').click();page.wait_for_url(base+'other.html');page.goto(base+'index.html')
            page.set_viewport_size({'width':390,'height':844});assert_grid_rows(page.locator('.pulse-stats a'), 2, 10)
            page.set_viewport_size({'width':1920,'height':1000});assert page.locator('.md-main__inner').evaluate('el=>el.getBoundingClientRect().width') <= 1920*.72
            page.get_by_role('button',name='Search hardware and news').click();page.get_by_role('searchbox',name='Universal search query').fill('kit');page.locator('.pulse-universal-dialog a').filter(has_text=re.compile(r'^kit/chip$')).locator("xpath=self::a[preceding-sibling::h3[1][starts-with(normalize-space(.), 'Board targets (')]]").wait_for();page.keyboard.press('Escape');assert not page.locator('.pulse-universal-dialog').is_visible()
            page.goto(base+'board.html');page.locator('.pulse-news-row').first.wait_for();assert page.locator('.pulse-news-detail:visible').count()==0
            profile=page.locator('.pulse-news-row .pulse-board-profile-link').first;profile.wait_for();profile.click();page.wait_for_url('**/boards/*.html');page.get_by_text('Target capability matrix',exact=True).wait_for();page.go_back();page.locator('.pulse-news-row').first.wait_for()
            page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-news-row').first.evaluate("el=>getComputedStyle(el).display")=='grid'
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
    print('Rendered Zensical site smoke test passed.')
if __name__=='__main__':main()
