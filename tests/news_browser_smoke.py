"""Exercise the portable news UI directly in Chromium, without a running website."""
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright
from browser_geometry import assert_grid_rows
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_news_table

def check_geometry(page):
    root=page.locator('.pulse-news-table').first
    g=root.evaluate("""el=>{const h=el.querySelector('thead th'),c=el.querySelector('.pulse-news-row:not([hidden]) .pulse-news-expand'),b=c.querySelector('button'),r=c.getBoundingClientRect(),br=b.getBoundingClientRect(),rem=parseFloat(getComputedStyle(document.documentElement).fontSize);return {headerDisplay:getComputedStyle(h).display,headerPosition:getComputedStyle(h).position,headerWidth:h.getBoundingClientRect().width,cellWidth:r.width,centerError:Math.abs(r.x+r.width/2-br.x-br.width/2),font:parseFloat(getComputedStyle(b).fontSize),rem};}""")
    assert g['cellWidth'] <= 2*g['rem']+2,g
    assert g['centerError'] <= 2,g
    assert g['font'] >= g['rem'],g
    if page.viewport_size['width']>768:
        assert g['headerDisplay']=='table-cell' and g['headerPosition']!='absolute',g
        assert abs(g['headerWidth']-g['cellWidth'])<=2,g
    return g

def main():
    row=dict(sha='a'*40,kind='board',subject='test',detail='evidence',path='boards/a/kit.yaml',committed='2026-11-26T17:00:00Z',confidence='observed')
    records=[dict(row,subject=f'Item {i:03d}',kind='dts' if i%2 else 'board',change_type='API documentation' if i%2 else 'New board') for i in range(205)]
    html='<html><body><header><a class="md-header__button md-logo">Old logo</a><span class="md-header__title">Zephyr Pulse</span></header>'+render_news_table(records)+'</body></html>'
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']};exe=shutil.which('chromium')
        if exe:args['executable_path']=exe
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.set_default_timeout(5000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(html);page.add_style_tag(content=(ROOT/'docs/assets/pulse.css').read_text())
        assert page.locator('.pulse-news-detail:visible').count()==205 # no-JS fallback
        assert not page.locator('.md-header__button.md-logo').is_visible();assert page.get_by_text('Zephyr Pulse',exact=True).is_visible()
        check_geometry(page)
        page.add_script_tag(content=(ROOT/'docs/assets/table-controls.js').read_text());page.add_script_tag(content=(ROOT/'docs/assets/news.js').read_text());assert page.locator('.pulse-news-row:visible').count()==100;assert page.locator('.pulse-news-detail:visible').count()==0
        first=page.locator('.pulse-news-row:visible').first;first.locator('.pulse-news-col-3').click();assert page.locator('.pulse-news-detail:visible a').count()==3;first.locator('button').press('Enter');assert page.locator('.pulse-news-detail:visible').count()==0
        first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==1;first.locator('.pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==100;page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==100;page.get_by_role('button',name='Next').click();assert page.locator('.pulse-news-row:visible').count()==5
        page.get_by_label('Rows per page').select_option('all');assert page.locator('.pulse-news-row:visible').count()==205
        page.get_by_label('Change type',exact=True).select_option('API documentation');assert page.locator('.pulse-news-row:visible').count()==102
        page.get_by_label('Change type',exact=True).select_option('');page.get_by_label('Sort by').select_option('change_type');assert page.locator('.pulse-news-row:visible').first.get_attribute('data-change-type')=='API documentation'
        page.get_by_label('Sort by').select_option('newest')
        page.locator('.pulse-news-controls select').first.select_option('dts');assert page.locator('.pulse-news-row:visible').count()==102
        page.locator('.pulse-news-controls select').first.select_option('');page.get_by_label('Filter news').fill('Item 042');assert page.locator('.pulse-news-row:visible').count()==1
        page.get_by_role('button',name='Expand page').click();assert page.locator('.pulse-news-detail:visible').count()==1;page.get_by_role('button',name='Collapse page').click();assert page.locator('.pulse-news-detail:visible').count()==0
        page.set_viewport_size({'width':390,'height':844});assert page.locator('.pulse-news-row:visible').first.evaluate('el=>getComputedStyle(el).display')=='grid';assert not errors,errors
        check_geometry(page)
        # Exercise the browser-generated table (the default category-page path).
        page.set_viewport_size({'width':1440,'height':900})
        page.evaluate("""records=>{const mount=document.createElement('div');document.body.replaceChildren(mount);PulseNews.render(mount,records,new Map(),records.length);}""",records)
        assert page.locator('.pulse-news-row:visible').count()==100
        page.get_by_label('Change type',exact=True).select_option('API documentation');assert page.locator('.pulse-news-row:visible').count()==100
        page.get_by_label('Change type',exact=True).select_option('');
        for width in (2048,1440,1024,390):
            page.set_viewport_size({'width':width,'height':900});g=check_geometry(page);print(f"Generated table {width}px: expand cell {g['cellWidth']:.1f}px, glyph font {g['font']:.1f}px")
        page.set_viewport_size({'width':1440,'height':900})
        first=page.locator('.pulse-news-row:visible').first
        first.locator('.pulse-news-toggle').click();assert page.locator('.pulse-news-detail:visible').count()==1
        assert first.locator('button').get_attribute('aria-expanded')=='true'
        page.get_by_role('button',name='Subject / target').click();assert page.locator('.pulse-news-detail:visible').count()==1
        first.locator('.pulse-news-toggle').press('Enter');assert page.locator('.pulse-news-detail:visible').count()==0
        # Test profile links and the separate exact filter without network access.
        board={'id':'kit','name':'kit','full_name':'Test Kit','folder':'boards/a/kit','slug':'kit-abc','url':'boards/kit-abc.html','targets':['kit/chip'],'socs':['chip'],'vendor':'a'}
        event=dict(row,subject='kit/chip',path='boards/a/kit/kit.yaml',boards=['kit'],board_profile_url=board['url'])
        other=dict(row,subject='unrelated',kind='driver',boards=[])
        for dynamic in (False,True):
            if dynamic:
                page.evaluate("""([e,o,b])=>{const mount=document.createElement('div');document.body.replaceChildren(mount);PulseNews.render(mount,[e,o],new Map([[b.id,b]]));}""",[event,other,board])
            else:
                page.evaluate("html=>{document.body.innerHTML=html;PulseNews.init(document.querySelector('[data-pulse-news]'));}",render_news_table([event,other],boards={'kit':board}))
            profile=page.locator('.pulse-news-row .pulse-board-profile-link');assert profile.count()==1;assert profile.get_attribute('href')==board['url']
            # Capture the actual click target while preventing navigation in this isolated fixture.
            page.evaluate("""()=>{window.profileClick=null;document.querySelector('.pulse-board-profile-link').addEventListener('click',e=>{window.profileClick=e.currentTarget.getAttribute('href');e.preventDefault();});}""")
            profile.click();assert page.evaluate('window.profileClick')==board['url'];assert page.locator('.pulse-news-row:visible').count()==2
            page.locator('.pulse-news-row').first.locator('.pulse-news-toggle').click()
            actions=page.locator('.pulse-news-detail:visible .pulse-news-links')
            for glyph in ('commit','github','board','search'):
                item=actions.locator('a').filter(has=page.locator('.pulse-i-'+glyph));assert item.count()==1,glyph
                assert item.locator('.pulse-icon').get_attribute('aria-hidden')=='true'
                assert item.locator('.pulse-icon').evaluate("el=>getComputedStyle(el).maskImage")!='none'
            assert actions.locator('a').filter(has=page.locator('.pulse-i-board')).get_attribute('href')==board['url']
            assert actions.locator('a').filter(has=page.locator('.pulse-i-github')).get_attribute('href').endswith(event['path'])
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':900})
                assert actions.evaluate("el=>el.scrollWidth<=el.clientWidth+1"),width
            page.set_viewport_size({'width':1440,'height':900})
            page.locator('.pulse-news-detail:visible .pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==1
            page.locator('.pulse-news-detail:visible .pulse-subject-filter').click();assert page.locator('.pulse-news-row:visible').count()==2
        # Watchlist chips and visible subject links must be independently selectable.
        page.evaluate("""([e,b])=>{document.body.innerHTML='<div id="pulse-home-watch"></div><div id="pulse-home-fallback">fallback</div>';window.PulsePreferences={load:async()=>({data:{boards:[b],events:[e]},store:{get:()=>({boards:['kit'],vendors:[],peripherals:[],home_limit:8})}})};}""",[event,board])
        page.add_script_tag(content=(ROOT/'docs/assets/intelligence.js').read_text().replace("new URL('./', document.currentScript.src)","new URL('https://pulse.test/assets/')"))
        page.locator('#pulse-home-watch').get_by_test_id('watch-tag').filter(has_text='kit').wait_for()
        assert page.locator('#pulse-home-watch .pulse-news-row .pulse-board-profile-link').get_attribute('href')==board['url']
        assert page.locator('#pulse-home-fallback').is_hidden()
        # Actual generated dashboard markup, not an independently drawn mock-up.
        from tempfile import TemporaryDirectory
        from pulse import connect,render,UTC
        import datetime as dt
        import re
        with TemporaryDirectory() as tmp:
            docs=Path(tmp)/'docs';db=connect(Path(tmp)/'fixture.sqlite')
            render(db,docs,dt.datetime.now(UTC),72,'https://example.invalid/');db.close()
            dashboard=re.search(r'<div class="pulse-stats">.*?</div>',(docs/'index.md').read_text(),re.S).group()
        page.evaluate('html=>{document.body.innerHTML=html}',dashboard)
        assert page.locator('.pulse-stats a').count()==10;assert page.locator('.pulse-stats a[href="other.html"]').count()==1
        for width,columns in ((2048,5),(1440,5),(1024,5),(390,2),(320,1)):
            page.set_viewport_size({'width':width,'height':900});assert_grid_rows(page.locator('.pulse-stats a'), columns, 10)
        # Exercise the actual settings builder and fieldset geometry without a server.
        page.evaluate("""()=>{document.body.innerHTML='<div id="pulse-settings"></div>';window.fetch=async()=>({ok:true,json:async()=>({preferences:{},watchlist:{},comparison:{snapshots:[]}})});}""")
        page.add_script_tag(content=(ROOT/'docs/assets/preferences.js').read_text().replace("new URL('../',document.currentScript.src)", "new URL('https://pulse.test/')"))
        page.locator('.pulse-settings-card').first.wait_for()
        assert page.locator('.pulse-settings-card').count()==4
        fields=page.locator('.pulse-settings-card').first.locator('.pulse-setting-field')
        for width,columns in ((1440,2),(390,1),(1440,2)):
            page.set_viewport_size({'width':width,'height':900});assert_grid_rows(fields, columns, 3)
        print('Settings geometry passed: desktop 2 columns, mobile 1, desktop 2.')
        assert not errors,errors
        browser.close()
    print('Direct Chromium news table test passed: logo CSS, fallback, 205 rows, expansion, pagination, filters, mobile.')
if __name__=='__main__':main()
