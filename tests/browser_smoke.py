"""Optional real-browser test: python tests/browser_smoke.py (Playwright + Chromium).
Uses a synthetic static site (mocked HTTP responses) with the same mounts as the generated pages.
Does not require a static site generator or make external network requests.
"""
import json
from pathlib import Path
import shutil
import tempfile
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import mimetypes

ROOT=Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);shutil.copytree(ROOT/'docs/assets',root/'assets')
        def target(id,features):
            return {'id':id,'board_id':id,'board':id,'name':id,'vendor':'test','vendor_name':'Test','socs':[id],'target':id,'url':'boards.html','metadata':{'features':features,'path':'boards/test/kit.yaml','arch':'arm','ram':256,'flash':1024},'releases':[{'tag':'v4.0.0','found':True,'features':['can'],'path':'boards/test/kit.yaml'}],'last_milestone':None,'milestone_count':0,'vendor_commits':None,'vendor_last':None}
        def event(id):return {'subject':id,'detail':id,'path':'boards/test/kit.yaml','sha':'a'*40,'committed':'2026-01-01T10:00:00Z','kind':'board','confidence':'observed','boards':[]}
        data={'head':'a'*40,'watchlist':{'boards':['*mcxn*'],'vendors':[],'peripherals':[]},'preferences':{'requirements':['can-fd']},'boards':[],'events':[event('mcxn947'),event('ra8p1'),event('unwatched')],'vendors':[],'coverage':{'complete':True},'comparison':{'features':['can','can-fd','ethernet'],'targets':[target('mcxn947',['can','ethernet']),target('ra8p1',['can','can-fd'])],'snapshots':[{'tag':'v4.0.0','latest_stable':True,'lts':False,'lifecycle':'Stable'}]}}
        (root/'intelligence.json').write_text(json.dumps(data))
        scripts=''.join(f'<script src="assets/{s}.js"></script>' for s in ['theme-zensical','preferences','intelligence','comparator','hardware-search','news'])
        import sys
        sys.path.insert(0,str(ROOT))
        from pulse import CATEGORIES
        from news_table import render_news_table
        news_fixture=render_news_table([dict(event(f'Event {i:03d}'),committed=f'2026-01-01T10:{i%60:02d}:00Z',commit_subject=f'Headline {i:03d}') for i in range(205)])
        for name,body in {'index':'<div id="pulse-home-watch"></div><div id="pulse-home-fallback">server fallback</div><section id="global">mcxn947 ra8p1 unwatched</section>','compare':'<div id="pulse-comparator"></div>','settings':'<div id="pulse-settings"></div>','watchlist':'<div id="pulse-watchlist"></div>','hardware-search':'<div id="pulse-hardware-search"></div>','news':news_fixture}.items():
            (root/(name+'.html')).write_text('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="assets/pulse.css"><body>'+body+scripts+'</body>')
        base='https://pulse.test/'
        with sync_playwright() as pw:
            args={'headless':True,'args':['--no-sandbox']};exe=shutil.which('chromium');
            if exe:args['executable_path']=exe
            browser=pw.chromium.launch(**args);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def fixture(route):
                path=root/urlparse(route.request.url).path.lstrip('/')
                if path.is_file():route.fulfill(status=200,body=path.read_bytes(),content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:route.fulfill(status=404,body='not found')
            page.route(base+'**',fixture)
            page.goto(base+'settings.html');page.get_by_label('Board / SoC patterns (comma separated)').fill('ra8P1');page.get_by_role('button',name='Save preferences').click();page.get_by_text('Saved in this browser.').wait_for()
            page.goto(base+'index.html');page.locator('#pulse-home-watch').get_by_text('ra8p1',exact=True).wait_for();assert not page.locator('#pulse-home-fallback').is_visible();assert 'unwatched' in page.locator('#global').inner_text();assert 'mcxn947' not in page.locator('#pulse-home-watch').inner_text()
            page.goto(base+'compare.html');page.get_by_role('button',name='Add',exact=True).first.wait_for();page.get_by_role('button',name='Add',exact=True).first.click();page.get_by_role('button',name='Add',exact=True).click();page.get_by_text('2 / 8 selected targets').wait_for();assert page.locator('.pulse-state').count()>0
            page.reload();page.get_by_text('2 / 8 selected targets').wait_for();page.get_by_label('Compare source metadata at').select_option('v4.0.0');page.get_by_text('0/1 with evidence · 0 YAML · 0 DTS hints',exact=True).first.wait_for();assert page.get_by_text('0/1 with evidence · 0 YAML · 0 DTS hints',exact=True).count()==2
            page.goto(base+'settings.html');page.get_by_text('2 selected targets.').wait_for();assert page.get_by_label('Comparison baseline').input_value()=='v4.0.0';assert page.get_by_label('Board / SoC patterns (comma separated)').input_value()=='ra8P1'
            with page.expect_download() as download:page.get_by_role('button',name='Export JSON').click()
            exported=json.loads(Path(download.value.path()).read_text());assert len(exported['preferences']['selected'])==2
            page.on('dialog',lambda dialog:dialog.accept());page.get_by_role('button',name='Restore published defaults').click();page.get_by_text('Restored published defaults.').wait_for();assert page.get_by_label('Board / SoC patterns (comma separated)').input_value()=='*mcxn*'
            page.locator('input[type=file]').set_input_files({'name':'preferences.json','mimeType':'application/json','buffer':json.dumps(exported).encode()});page.get_by_text('Imported and saved.').wait_for();assert page.get_by_label('Board / SoC patterns (comma separated)').input_value()=='ra8P1';assert not errors,errors
            page.goto(base+'hardware-search.html');page.get_by_label('Find hardware or news (comma = OR)').fill('*mcxn*');page.locator('.pulse-search-result h3').get_by_text('mcxn947',exact=True).first.wait_for();page.wait_for_timeout(200);assert 'ra8p1' not in page.locator('.pulse-search-result').all_inner_texts().__str__();page.reload();assert page.get_by_label('Find hardware or news (comma = OR)').input_value()=='*mcxn*';assert not errors,errors
            page.goto(base+'news.html');page.locator('.pulse-news-controls').wait_for();assert page.locator('.pulse-news-row:visible').count()==100;assert page.locator('.pulse-news-detail:visible').count()==0
            row=page.locator('.pulse-news-row:visible').first;row.locator('.pulse-news-col-2').click();assert page.locator('.pulse-news-detail:visible').count()==1;assert page.locator('.pulse-news-detail:visible a').count()==2
            row.locator('button').press('Enter');assert page.locator('.pulse-news-detail:visible').count()==0
            page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==100;page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==5
            page.get_by_label('Rows per page').select_option('all');assert page.locator('.pulse-news-row:visible').count()==205
            page.get_by_label('Filter news').fill('Headline 042');assert page.locator('.pulse-news-row:visible').count()==1;page.get_by_role('button',name='Expand page').click();assert page.locator('.pulse-news-detail:visible').count()==1;page.get_by_role('button',name='Collapse page').click();assert page.locator('.pulse-news-detail:visible').count()==0
            page.get_by_label('Filter news').fill('');page.get_by_label('Sort by').select_option('subject');assert 'Event 000' in page.locator('.pulse-news-row:visible').first.inner_text();assert not errors,errors
            browser.close()
    print('Browser smoke test passed: settings, watchlist, global news, comparator, reload, export/reset/import.')
if __name__=='__main__':main()
