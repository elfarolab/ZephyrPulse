"""Exercise the *actual* generated Zensical site after CI builds the Git fixture."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(ROOT/'site')))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_viewport_size({'width':1440,'height':900});page.goto(base+'settings.html');page.locator('.pulse-settings-card').first.wait_for();assert page.locator('.pulse-settings-card').count()==4
            assert page.locator('.pulse-settings-card').first.evaluate("el=>getComputedStyle(el).gridTemplateColumns.split(' ').length") == 2
            page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-settings-card').first.evaluate("el=>getComputedStyle(el).gridTemplateColumns.split(' ').length") == 1
            page.set_viewport_size({'width':1440,'height':900});page.get_by_label('Board / SoC patterns (comma separated)').fill('*kit*');page.get_by_role('button',name='Save preferences').click();page.get_by_text('Saved in this browser.').wait_for()
            page.goto(base+'compare.html');page.get_by_role('button',name='Add',exact=True).first.click();page.get_by_text('1 / 8 selected targets').wait_for()
            page.goto(base+'hardware-search.html');page.get_by_label('Find hardware or news (comma = OR)').fill('*kit*');page.get_by_label('Result type').select_option('target');page.locator('.pulse-search-result h3').get_by_text('kit/chip',exact=True).wait_for();page.reload();page.locator('.pulse-search-result h3').get_by_text('kit/chip',exact=True).wait_for();assert page.get_by_label('Find hardware or news (comma = OR)').input_value()=='*kit*'
            page.locator('.pulse-search-result h3 a').first.click();page.get_by_text('Target capability matrix',exact=True).wait_for();assert not errors,errors
            page.goto(base+'index.html');page.set_viewport_size({'width':1440,'height':900});page.locator('.md-tabs').wait_for(state='visible');page.evaluate('window.scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(350);assert page.locator('.md-tabs').is_visible();assert not page.locator('.md-sidebar--secondary').count() or not page.locator('.md-sidebar--secondary').is_visible();page.locator('#pulse-home-watch').get_by_text('Your browser watchlist').wait_for();assert page.get_by_role('link',name='Hardware search',exact=True).count()>0
            assert page.locator('.pulse-stats .pulse-stat-symbol .pulse-icon').count()==8
            assert page.locator('.pulse-tools a .pulse-icon').count()==4
            assert page.locator('.md-tabs__link .pulse-icon').count()==6
            assert not page.locator('.md-sidebar--primary').count() or not page.locator('.md-sidebar--primary').is_visible()
            assert page.locator('.pulse-stats .pulse-icon').first.evaluate("el=>getComputedStyle(el).maskImage!=='none'")
            assert page.locator('.md-header__button.md-logo:visible').count()==0
            table=page.locator('.pulse-news-table').last;table.locator('.pulse-news-row').first.wait_for();assert table.locator('.pulse-news-detail:visible').count()==0
            table.locator('.pulse-news-row').first.locator('button').click();assert table.locator('.pulse-news-detail:visible a').count()>0
            page.goto(base+'board.html');page.locator('.pulse-news-row').first.wait_for();assert page.locator('.pulse-news-detail:visible').count()==0
            page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-news-row').first.evaluate("el=>getComputedStyle(el).display")=='grid'
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
    print('Rendered Zensical site smoke test passed.')
if __name__=='__main__':main()
