"""Variable-column category tables: sorting, scopes, mixed categories and lazy details."""
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_grouped_news, render_board_timeline
from test_news_groups import event


def main():
    a=event(kind='soc',sha='a'*40,path='soc/acme/zeta/a.c',commit_subject='soc: zeta: fix clock')
    b=event(kind='soc',sha='b'*40,path='soc/acme/alpha/a.c',commit_subject='soc: alpha: add support')
    c=dict(a,path='soc/acme/zeta/b.c',subject='b.c')
    doc=dict(a,kind='docs',path='doc/zeta.rst',subject='zeta docs')
    drv=dict(b,kind='driver',path='drivers/i2c/i2c_omap.c',subject='i2c_omap.c')
    board={'id':'kit','name':'kit','full_name':'Kit','folder':'boards/acme/kit','slug':'kit-abc','url':'boards/kit-abc.html','targets':['kit/chip'],'socs':['chip'],'vendor':'acme'}
    board_event=dict(a,kind='board_feature',subject='kit',path='boards/acme/kit/kit.yaml',boards=['kit'],board_profile_url=board['url'],detail='New supported metadata entry: can')
    manifests={a['sha']:[dict(path=p,revision=a['sha'],status='M') for p in (a['path'],c['path'],doc['path'],board_event['path'])],b['sha']:[dict(path=b['path'],revision=b['sha'],status='M')]}
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def mount(category,rows,static):
            page.set_content('<html><body><main id="mount">'+(render_grouped_news(rows,category,boards={'kit':board},commit_files=manifests) if static else '')+'</main></body></html>')
            page.add_style_tag(content=(ROOT/'docs/assets/pulse.css').read_text())
            for script in ('table-controls.js','news.js'):page.add_script_tag(content=(ROOT/'docs/assets'/script).read_text())
            if not static:page.evaluate('([category,rows,manifests,board])=>PulseNews.renderGrouped(document.getElementById("mount"),rows,new Map([[board.id,board]]),category,manifests)',[category,rows,manifests,board])
        for static in (True,False):
            mount('soc',[a,c,b],static)
            visible=page.locator('.pulse-news-row:visible');expect(visible).to_have_count(2)
            assert not page.get_by_label('Category',exact=True).is_visible()
            assert page.locator('thead th').count()==7
            assert page.locator('thead th[data-news-column="1"]').count()==0
            assert page.locator('.pulse-news-col-2 a').count()==0
            page.get_by_role('button',name='SoC / family',exact=True).click();expect(visible.first.locator('.pulse-news-col-2')).to_have_text('soc/acme/alpha')
            page.get_by_role('button',name='Files',exact=True).click();expect(visible.first.locator('.pulse-news-col-4')).to_have_text('1')
            page.get_by_role('button',name='Files',exact=True).click();expect(visible.first.locator('.pulse-news-col-4')).to_have_text('4')
            page.get_by_label('SoC / family',exact=True).select_option('soc/acme/zeta');expect(visible).to_have_count(1)
            if not static:expect(page.locator('.pulse-affected-files')).to_have_count(0)
            page.get_by_label('Filter news').fill('doc/zeta.rst');expect(visible).to_have_count(1)
            visible.first.locator('.pulse-news-col-6 button').click();expect(page.locator('.pulse-news-detail:visible .pulse-affected-files > li')).to_have_count(4)
            expect(page.locator('.pulse-news-detail:visible').get_by_role('link',name='doc/zeta.rst')).to_be_visible()
            page.get_by_label('Sort by').select_option('headline');expect(page.locator('th[data-news-column="3"]')).to_have_attribute('aria-sort','ascending')
            page.set_viewport_size({'width':390,'height':844});expect(visible.first.locator('.pulse-news-col-3 button')).to_be_visible();expect(visible.first.locator('.pulse-news-col-6 button')).to_be_visible()
            page.set_viewport_size({'width':1440,'height':900})
            mount('docs',[doc,dict(doc,sha=b['sha'],path='doc/alpha.rst',commit_subject='doc: alpha')],static)
            expect(page.locator('thead th')).to_have_count(6);assert page.locator('.pulse-news-col-2').count()==0
            page.get_by_role('button',name='Commit description',exact=True).click();expect(visible.first.locator('.pulse-news-col-3')).to_have_text('doc: alpha')
            page.get_by_role('button',name='Commit description',exact=True).click();expect(visible.first.locator('.pulse-news-col-3')).to_have_text(a['commit_subject']) # d vs s
            mount('all',[a,doc,b,drv],static);expect(visible).to_have_count(2)
            assert page.get_by_label('Category',exact=True).is_visible()
            page.get_by_label('Category',exact=True).select_option('docs');expect(visible).to_have_count(1);expect(visible.first.locator('.pulse-news-col-1')).to_contain_text('Documentation')
            page.get_by_label('Category',exact=True).select_option('driver');expect(visible).to_have_count(1);expect(visible.first.locator('.pulse-news-col-1')).to_contain_text('Drivers')
            mount('board_feature',[board_event,dict(board_event,detail='New supported metadata entry: spi')],static)
            expect(visible).to_have_count(2);expect(page.locator('.pulse-signal-preview')).to_have_count(2)
            expect(page.locator('.pulse-board-profile-link')).to_have_count(2)
            assert not errors,errors
        a=dict(sha='a'*40,committed='2026-11-27T02:26:00Z',label='CAN',confidence='observed',path='boards/a/kit/a.dts')
        b=dict(a,label='SPI',path='boards/a/kit/b.dts')
        page.set_content(render_board_timeline([a,b,dict(a,sha='b'*40,label='UART')],{},lambda s:'Unknown'))
        page.add_script_tag(content=(ROOT/'docs/assets/table-controls.js').read_text());expect(page.locator('tbody tr')).to_have_count(2)
        page.get_by_role('button',name='Evidence',exact=True).click();expect(page.locator('tbody tr').first.locator('summary')).to_have_text('1 milestone')
        page.get_by_role('button',name='Evidence',exact=True).click();expect(page.locator('tbody tr').first.locator('summary')).to_have_text('2 milestones')
        page.locator('tbody tr').first.locator('summary').click();expect(page.get_by_role('link',name='boards/a/kit/b.dts')).to_be_visible()
        browser.close()
    print('Category layouts, semantic sorting, scope filters, lazy file details, mixed categories and board timeline passed.')
if __name__=='__main__':main()
