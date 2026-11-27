"""One-line summaries at narrow and wide sizes, including evidence and age badges."""
import datetime as dt
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_grouped_news, render_news_table
from test_news_groups import event


def main():
    now=dt.datetime(2026,11,27,15,0,tzinfo=dt.timezone.utc)
    board='very_long_board_name_for_a_test/very_long_soc_name/cpu0/long_variant'
    title='zeta: '+('long commit description with technical words '*12).strip()
    e=event(kind='board_feature',subject=board,commit_subject=title,path='boards/a/kit/kit.yaml',detail='New supported metadata entry: specialdetail123',committed=now.isoformat())
    candidate=dict(e,kind='board_candidate',subject='boards/a/kit',path='boards/a/kit/kit.dts',detail='Potential support specialcandidate456')
    declared=dict(e,sha='b'*40,commit_subject='alpha: declared support',detail='New supported metadata entry: uart',committed=(now-dt.timedelta(hours=7)).isoformat())
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.clock.install(time=now)
        def mount(html):
            page.set_content('<html><body data-md-color-scheme="default"><main class="md-content md-typeset"><div id="mount">'+html+'</div></main></body></html>')
            page.add_style_tag(path=ROOT/'docs/assets/pulse.css')
            for name in ('table-controls.js','news.js','theme-zensical.js'):page.add_script_tag(path=ROOT/'docs/assets'/name)
        def geometry(rows):
            heights=rows.evaluate_all('rs=>rs.map(r=>r.getBoundingClientRect().height)')
            assert max(heights)-min(heights)<2,heights
            assert max(heights)<=34,heights
            assert rows.evaluate_all('rs=>rs.every(r=>[...r.cells].every(c=>getComputedStyle(c).whiteSpace==="nowrap"))')
        for static in (True,False):
            mount(render_grouped_news([e,candidate,declared],'board_feature') if static else '')
            if not static:page.evaluate('rows=>PulseNews.renderGrouped(document.getElementById("mount"),rows,new Map(),"board_feature",{})',[e,candidate,declared])
            visible=page.locator('.pulse-news-row:visible');expect(visible).to_have_count(2)
            newest=visible.first;expect(newest.locator('.pulse-evidence-badge')).to_have_text('Possible support +1')
            expect(newest.locator('.pulse-fresh-badge')).to_have_count(1)
            assert 'specialdetail123' not in newest.inner_text() and 'specialcandidate456' not in newest.inner_text()
            assert newest.locator('.pulse-news-col-3').get_attribute('title')==title
            for width in (2048,1440,1024,390):
                page.set_viewport_size({'width':width,'height':900});geometry(visible)
                assert newest.locator('.pulse-news-expand').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
                assert newest.locator('.pulse-news-expand').evaluate('el=>{const a=el.querySelector("button").getBoundingClientRect(),b=el.querySelector(".pulse-fresh-badge").getBoundingClientRect();return Math.abs(a.y+a.height/2-b.y-b.height/2)<3&&a.right<=b.left+1;}')
                assert newest.locator('.pulse-commit-summary').evaluate('el=>{const b=el.querySelector(".pulse-evidence-badge"),t=el.querySelector("button");return b.getBoundingClientRect().right<=t.getBoundingClientRect().left&&t.scrollWidth>t.clientWidth}')
                if width==390:
                    assert page.locator('.pulse-news-scroll').evaluate('el=>el.scrollWidth>el.clientWidth&&el.clientWidth<=innerWidth')
                    assert newest.locator('.pulse-news-col-6').is_visible()
            page.set_viewport_size({'width':1440,'height':900})
            page.get_by_role('button',name='Commit description',exact=True).click();expect(visible.first.locator('.pulse-commit-expand').first).to_have_text('alpha: declared support')
            page.get_by_role('button',name='Commit description',exact=True).click();expect(visible.first.locator('.pulse-commit-expand').first).to_have_text(title)
            page.get_by_label('Filter news').fill('specialdetail123');expect(visible).to_have_count(1)
            page.get_by_label('Evidence type').select_option('Possible support');expect(visible).to_have_count(1)
            visible.first.locator('.pulse-news-toggle').click();panel=page.locator('.pulse-news-detail:visible');expect(panel.locator('.pulse-evidence-summary')).to_contain_text('Declared metadata');expect(panel).to_contain_text('specialcandidate456');expect(panel).to_contain_text(title)
            page.get_by_label('Evidence type').select_option('');page.get_by_label('Filter news').fill('')
        # Every grouped layout and the ungrouped watchlist use the same compact rules.
        for kind in ('board','board_change','soc','sensor','driver','dts','dt_bindings','subsys','samples','tests','manifest','kernel','docs','other','all','release_news'):
            record=dict(e,kind=kind if kind not in ('all','release_news') else 'board_change')
            short=dict(record,sha='c'*40,commit_subject='short',subject='kit',committed=(now-dt.timedelta(hours=30)).isoformat())
            mount(render_grouped_news([record,short],kind));geometry(page.locator('.pulse-news-row:visible'))
        mount(render_news_table([e,declared]));geometry(page.locator('.pulse-news-row:visible'))
        # Comparator cells keep the evidence state and an inline source count, with
        # all original compatible/status links behind a native disclosure.
        mount('<div id="pulse-comparator"></div>')
        page.evaluate("""()=>{const prefs={selected:['a'],requirements:['can'],baseline:'main',comparison_rows:'required',search:'',matches_only:false};window.PulsePreferences={node:(t,s)=>{let e=document.createElement(t);if(s!==undefined)e.textContent=s;return e},link:(s,h)=>{let a=document.createElement('a');a.textContent=s;a.href=h;return a},button:(s,f)=>{let b=document.createElement('button');b.textContent=s;b.onclick=f;return b},split:s=>s.split(',').filter(Boolean),defaults:prefs,load:async()=>({data:{head:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',comparison:{features:['can'],snapshots:[],targets:[{id:'a',board_id:'a',name:'Kit',target:'kit/chip',vendor:'acme',vendor_name:'Acme',socs:['chip'],metadata:{features:['can'],path:'boards/a/kit/kit.yaml',dts_evidence:{nodes:[{features:['can'],compatible:'test,can',compatible_paths:['dts/test.dtsi'],status_paths:['dts/test.dtsi']},{features:['can'],compatible:'test,can2',compatible_paths:['dts/test2.dtsi'],status_paths:[]}]}},releases:[],url:'boards/kit.html'}]},coverage:{complete:true}},store:{get:()=>prefs,saved:()=>true,update:()=>true}})}}""")
        page.add_script_tag(path=ROOT/'docs/assets/comparator.js')
        disclosure=page.locator('.pulse-compare-evidence');expect(disclosure.locator('summary')).to_have_text('2 sources')
        assert disclosure.get_by_role('link',name='test,can',exact=True,include_hidden=True).count()==1
        expect(disclosure.locator('ul')).not_to_be_visible()
        disclosure.locator('summary').click();expect(disclosure.get_by_role('link',name='test,can',exact=True)).to_be_visible();expect(disclosure.get_by_role('link',name='status',exact=True)).to_be_visible()
        disclosure.locator('summary').click();expect(disclosure.locator('ul')).not_to_be_visible()
        assert not errors,errors
        browser.close()
    print('Compact rows, inline evidence and freshness badges, full-title sorting, hidden evidence search, all grouped layouts and mobile scrolling passed.')

if __name__=='__main__':main()
