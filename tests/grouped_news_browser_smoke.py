"""Exercise the same grouped table in both static and browser-rendered modes."""
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_table import render_grouped_news
from test_news_groups import event


def main():
    rows=[];manifests={}
    for i in range(31):
        sha=f'{i+1:040x}'
        a=event(sha=sha,commit_subject=f'drivers: i2c: omap: change {i:02d}',committed=f'2026-11-27T02:{i:02d}:00Z')
        b=event(sha=sha,path='drivers/i2c/Kconfig.omap',commit_subject=a['commit_subject'],committed=a['committed'])
        rows.extend([a,b])
        manifests[sha]=[dict(path=p,revision=sha,status='M') for p in [a['path'],b['path'],*[f'doc/extra-{i}-{j}.rst' for j in range(i)]]]
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for static in (True,False):
            page.set_content('<html><body><main id="mount">'+(render_grouped_news(rows,'driver',commit_files=manifests) if static else '')+'</main></body></html>')
            page.add_style_tag(content=(ROOT/'docs/assets/pulse.css').read_text())
            page.add_script_tag(content=(ROOT/'docs/assets/table-controls.js').read_text());page.add_script_tag(content=(ROOT/'docs/assets/news.js').read_text())
            if not static:
                page.evaluate('([rows,manifests])=>PulseNews.renderGrouped(document.getElementById("mount"),rows,new Map(),"driver",manifests)',[rows,manifests])
            visible=page.locator('.pulse-news-row:visible');expect(visible).to_have_count(31)
            expect(page.locator('.pulse-group-summary')).to_contain_text('31 matching commits · 62 of 62 classified events')
            assert page.locator('.pulse-news-col-2 a').count()==0
            page.get_by_label('Rows per page').select_option('25');expect(visible).to_have_count(25)
            files=page.get_by_role('button',name='Files',exact=True)
            files.click();expect(visible.first.locator('.pulse-news-col-4')).to_have_text('2')
            files.click();expect(visible.first.locator('.pulse-news-col-4')).to_have_text('32')
            first=visible.first;first.locator('.pulse-news-col-6 button').click();detail=page.locator('.pulse-news-detail:visible');expect(detail).to_have_count(1)
            expect(detail.locator('.pulse-affected-files > li')).to_have_count(32)
            expect(detail.get_by_role('link',name='drivers/i2c/Kconfig.omap')).to_be_visible()
            expect(first.locator('.pulse-news-col-3 button')).to_have_attribute('aria-expanded','true')
            first.locator('.pulse-news-col-3 button').press('Enter');expect(detail).to_have_count(0)
            page.get_by_role('button',name='Next').click();expect(visible).to_have_count(6)
            expect(visible.last.locator('.pulse-news-col-4')).to_have_text('2')
            page.get_by_role('button',name='Commit description',exact=True).click();expect(visible.first.locator('.pulse-news-col-3')).to_contain_text('change 00')
            page.get_by_label('Filter news').fill('doc/extra-30-29.rst');expect(visible).to_have_count(1)
            expect(visible.first.locator('.pulse-news-col-3')).to_contain_text('change 30')
            page.get_by_label('Filter news').fill('');page.get_by_label('Subsystem',exact=True).select_option('i2c');page.get_by_label('Driver',exact=True).select_option('omap');expect(visible).to_have_count(25)
            page.get_by_role('button',name='Expand page').click();expect(detail).to_have_count(25)
            page.get_by_role('button',name='Collapse page').click();expect(detail).to_have_count(0)
            page.set_viewport_size({'width':390,'height':844});expect(visible.first.locator('.pulse-news-col-6 button')).to_be_visible()
            assert visible.first.evaluate("el=>getComputedStyle(el).display")=='grid'
            page.set_viewport_size({'width':1440,'height':900})
            assert not errors,errors
        browser.close()
    print('Grouped commits: exact files, header sorting across pages, filters, keyboard expansion and mobile passed (static + dynamic).')
if __name__=='__main__':main()
