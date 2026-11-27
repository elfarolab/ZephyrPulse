"""Direct browser regressions for shared table controls and contextual vendor links."""
from pathlib import Path
import shutil, sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from news_table import render_news_table
ASSETS=ROOT/'docs/assets'
def main():
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
        if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page();page.set_default_timeout(4000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def open_page(path,html):
            nonlocal page
            page.close();page=browser.new_page();page.set_default_timeout(5000);page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content('<html><head><base href="https://pulse.test/"></head><body>'+html+'</body></html>',wait_until='domcontentloaded');page.add_script_tag(content=(ASSETS/'table-controls.js').read_text());page.add_style_tag(content=(ASSETS/'pulse.css').read_text())
        vendor_table='<div id="pulse-vendor-filter"></div><table><thead><tr><th>Vendor</th><th>Commits</th></tr></thead><tbody><tr><td><a href="boards.html?vendor=nxp">nxp</a></td><td>12</td></tr><tr><td><a href="boards.html?vendor=nxp2">nxp2</a></td><td>2</td></tr></tbody></table><div id="pulse-vendor-trends"></div>'
        open_page('vendors.html?vendor=nxp',vendor_table)
        page.evaluate("""window.PulsePreferences={load:async()=>({data:{boards:[],vendors:[{vendor:'nxp',commits:12,last:'2026-11-26',daily:{}},{vendor:'nxp2',commits:2,last:'2026-11-26',daily:{}}],updated:'2026-11-26',coverage:{cutoff:'2026-11-25',complete:true}},store:{get:()=>({vendor:'nxp2'}),update:()=>{throw Error('unexpected save')}}})}""")
        # document.currentScript must be a URL; serve the original script with a route.
        page.add_script_tag(content=(ASSETS/'intelligence.js').read_text().replace("new URL('./', document.currentScript.src)","new URL('https://pulse.test/assets/')").replace('location.search',"'?vendor=nxp'"));page.locator('#pulse-vendor-filter button').wait_for();assert page.locator('tbody tr:visible').count()==1;assert page.locator('tbody tr:visible').inner_text().startswith('nxp\t');assert page.locator('select').input_value()=='nxp'
        page.get_by_role('button',name='Show all vendors').click();assert page.locator('tbody tr:visible').count()==2;assert page.locator('#pulse-vendor-filter button').is_hidden()
        page.get_by_role('button',name='Commits').click();assert page.locator('tbody tr').first.inner_text().endswith('2');page.get_by_role('button',name='Commits').click();assert page.locator('tbody tr').first.inner_text().endswith('12')
        row=dict(sha='a'*40,kind='driver',subject='test',detail='evidence',path='drivers/a.c',committed='2026-11-26T17:00:00Z',confidence='observed')
        records=[dict(row,subject=f'Item {i:03d}') for i in range(205)]
        open_page('driver.html',render_news_table(records));page.add_script_tag(content=(ASSETS/'news.js').read_text());page.locator('.pulse-news-controls').wait_for();page.get_by_role('button',name='Subject / target').click();assert page.locator('.pulse-news-row:visible').first.locator('.pulse-news-col-2').inner_text()=='Item 000';page.get_by_role('button',name='Subject / target').click();assert page.locator('.pulse-news-row:visible').first.locator('.pulse-news-col-2').inner_text()=='Item 204';page.locator('.pulse-news-row:visible').first.locator('button').click();assert 'Item 204' in page.locator('.pulse-news-detail:visible').inner_text();page.locator('.pulse-news-row:visible').first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==1;page.locator('.pulse-news-row:visible').first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==100
        open_page('boards.html?vendor=nxp','<div id="pulse-board-filter"></div><table><thead><tr><th>Board</th><th>Vendor</th><th>SoCs</th></tr></thead><tbody><tr><td><a href="boards/a.html">A</a></td><td>nxp</td><td><a href="boards.html?subject=chip">chip</a></td></tr><tr><td><a href="boards/b.html">B</a></td><td>nxp2</td><td>chip2</td></tr><tr><td><a href="boards/c.html">C</a></td><td>nxp</td><td>chip2</td></tr></tbody></table>')
        page.evaluate("""window.PulsePreferences={load:async()=>({data:{boards:[{id:'a',url:'boards/a.html',name:'A',vendor:'nxp',socs:['chip'],targets:[]},{id:'b',url:'boards/b.html',name:'B',vendor:'nxp2',socs:['chip2'],targets:[]},{id:'c',url:'boards/c.html',name:'C',vendor:'nxp',socs:['chip2'],targets:[]}]},store:{get:()=>({explorer_search:'no-match',explorer_watched:true,boards:[],vendors:[]}),update:()=>{throw Error('unexpected save')}}})}""")
        page.add_script_tag(content=(ASSETS/'intelligence.js').read_text().replace("new URL('./', document.currentScript.src)","new URL('https://pulse.test/assets/')").replace('location.search',"'?vendor=nxp'"));page.locator('.pulse-vendor-explorer').wait_for();assert page.locator('.pulse-vendor-group:visible').count()==1;assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==2
        page.get_by_role('link',name='chip',exact=True).click();assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==1;page.get_by_role('link',name='chip',exact=True).click();assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==2;page.locator('#pulse-board-filter button').first.click();assert page.locator('.pulse-vendor-group:visible').count()==2;assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==0
        page.get_by_role('button',name='Expand all vendors').click();assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==3
        page.get_by_role('button',name='Boards',exact=True).click();assert page.locator('.pulse-vendor-group').first.locator('td').nth(2).inner_text()=='1'
        page.get_by_role('button',name='Boards',exact=True).click();assert page.locator('.pulse-vendor-group').first.locator('td').nth(2).inner_text()=='2'
        page.get_by_role('button',name='Board',exact=True).first.click();page.get_by_role('button',name='Board',exact=True).first.click();assert page.locator('.pulse-vendor-boards tbody tr:visible').first.inner_text().startswith('C')
        page.get_by_role('button',name='Collapse all vendors').click();assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==0
        page.get_by_role('searchbox').fill('chip2');assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==2
        page.get_by_role('searchbox').fill('');assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==0
        page.get_by_role('button',name='Boards for nxp',exact=True).click();assert page.locator('.pulse-vendor-boards tbody tr:visible').count()==2
        page.set_viewport_size({'width':390,'height':844});assert page.get_by_role('link',name='A',exact=True).is_visible();assert page.locator('.pulse-vendor-explorer-scroll').evaluate('el=>el.clientWidth<=document.documentElement.clientWidth')
        open_page('compare.html','<div id="pulse-comparator"></div>')
        page.evaluate("""const prefs={selected:[],requirements:[],baseline:'main',comparison_rows:'all',search:'',matches_only:false};window.PulsePreferences={node:(t,s)=>{let e=document.createElement(t);if(s!==undefined)e.textContent=s;return e},link:(s,h)=>{let a=document.createElement('a');a.textContent=s;a.href=h;return a},button:(s,f)=>{let b=document.createElement('button');b.textContent=s;b.onclick=f;return b},split:s=>s.split(',').filter(Boolean),defaults:prefs,load:async()=>({data:{comparison:{features:[],snapshots:[],targets:Array.from({length:85},(_,i)=>({id:String(i),board_id:'b'+i,target:'Target '+String(i).padStart(3,'0'),vendor:'nxp',vendor_name:'NXP',socs:[],metadata:{features:[]},url:'boards/a.html'}))},coverage:{complete:true}},store:{get:()=>prefs,saved:()=>true,update:()=>true}})}""")
        page.add_script_tag(content=(ASSETS/'comparator.js').read_text());page.get_by_role('button',name='Exact target').wait_for();page.get_by_role('button',name='Exact target').click();assert page.locator('tbody tr').first.locator('th').inner_text()=='Target 000';page.get_by_role('button',name='Exact target').click();assert page.locator('tbody tr').first.locator('th').inner_text()=='Target 084';page.get_by_role('button',name='Next').click();assert page.locator('tbody tr').first.locator('th').inner_text()=='Target 044';assert page.locator('tbody tr').first.locator('th a').get_attribute('href')=='boards/a.html';page.get_by_role('button',name='Filter target Target 044',exact=True).click();assert page.locator('tbody tr').count()==1;page.get_by_role('button',name='Filter target Target 044',exact=True).click();assert page.locator('tbody tr').count()==40
        assert not errors,errors;browser.close()
    print('Contextual vendor and SoC filtering, numeric sort, full-dataset news and comparator sorting and expansion passed.')
if __name__=='__main__':main()
