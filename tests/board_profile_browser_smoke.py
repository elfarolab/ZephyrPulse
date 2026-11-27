"""Isolated browser check of actual generated board-profile markup and shared JS."""
from pathlib import Path
import shutil,sys
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_board_activity import BoardActivityTests

def main():
    # Use the same Git-backed fixture as the unit regression; inspect the generated markup.
    case=BoardActivityTests('test_board_profile_activity_and_stability');case.setUp()
    try:
        case.test_board_profile_activity_and_stability()
        page_text=next((case.root/'docs/boards').glob('*.md')).read_text()
        markup=page_text[page_text.index('<section class="pulse-board-overview"'):page_text.index('## Recent support timeline')]
        with sync_playwright() as pw:
            args={'headless':True,'args':['--no-sandbox']}
            if shutil.which('chromium'):args['executable_path']=shutil.which('chromium')
            browser=pw.chromium.launch(**args);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content('''<html><head><base href="https://fixture.invalid/boards/kit.html"></head><body><header><a class="md-header__button md-logo" href="../index.html">Logo</a><div class="md-header__title"><div class="md-header__topic"><span class="md-ellipsis">Zephyr Pulse</span></div><div class="md-header__topic"><span class="md-ellipsis">Other changes</span></div></div><a id="repo" href="https://github.com/zephyrproject-rtos/zephyr">Upstream Zephyr</a></header><main class="md-content md-typeset">'''+markup+'</main></body></html>')
            page.add_style_tag(path=ROOT/'docs/assets/pulse.css')
            for name in ('theme-zensical.js','table-controls.js','news.js'):page.add_script_tag(path=ROOT/'docs/assets'/name)
            home=page.get_by_role('link',name='Zephyr Pulse home');expect(home).to_have_attribute('href','https://fixture.invalid/index.html')
            # Simulate the classic theme's scrolled state, where the second topic
            # normally replaces the site name. The brand must remain clickable.
            page.add_style_tag(content=''' .md-header__title--active .md-header__topic:first-child {opacity:0;transform:translateX(-20px);pointer-events:none;} .md-header__title--active .md-header__topic:last-child {opacity:1;} ''')
            page.evaluate("document.querySelector('.md-header__title').classList.add('md-header__title--active')")
            expect(home).to_be_visible();expect(page.get_by_text('Other changes',exact=True)).not_to_be_visible()
            assert home.evaluate("el=>getComputedStyle(el.closest('.md-header__topic')).opacity")=='1'
            page.evaluate("document.querySelector('.pulse-home-title').addEventListener('click',e=>{e.preventDefault();e.currentTarget.dataset.clicked='yes'})")
            home.click();expect(home).to_have_attribute('data-clicked','yes')
            expect(page.locator('#repo')).to_have_attribute('target','_blank');expect(page.locator('#repo')).to_have_attribute('rel','noopener noreferrer')
            expect(page.locator('.pulse-board-overview-links a').first).to_have_attribute('target','_blank')
            assert not page.locator('.pulse-board-overview-meta dd a').first.get_attribute('target')
            targets=page.locator('.pulse-board-target');expect(targets).to_have_count(2);assert page.locator('.pulse-board-target[open]').count()==0
            targets.first.locator(':scope > summary').press('Enter');expect(targets.first.locator('table').first).to_be_visible();assert page.locator('.pulse-board-target[open]').count()==1
            expect(targets.first.locator('table').first.get_by_role('button',name='Peripheral / feature')).to_be_visible()
            targets.first.locator(':scope > summary').click();assert page.locator('.pulse-board-target[open]').count()==0
            rows=page.locator('.pulse-news-row:visible');expect(rows).to_have_count(2);expect(page.locator('.pulse-news-detail:visible')).to_have_count(0)
            page.get_by_role('button',name='Commit description',exact=True).click();rows.first.locator('.pulse-news-col-6 button').click()
            detail=page.locator('.pulse-news-detail:visible');expect(detail).to_have_count(1);expect(detail.get_by_role('link',name='doc/mixed.rst')).to_have_attribute('target','_blank')
            expect(detail.get_by_role('link',name='View upstream commit')).to_have_attribute('rel','noopener noreferrer')
            page.evaluate("document.querySelector('main').insertAdjacentHTML('beforeend','<a id=dynamic href=https://example.com/>external</a>')")
            expect(page.locator('#dynamic')).to_have_attribute('target','_blank')
            page.evaluate("document.querySelector('#dynamic').href='../boards.html'")
            expect(page.locator('#dynamic')).not_to_have_attribute('target','_blank')
            page.set_viewport_size({'width':390,'height':844});expect(rows.first.locator('.pulse-news-col-6 button')).to_be_visible();assert not errors,errors
            browser.close()
    finally:case.doCleanups()
    print('Board profile activity, closed target disclosures, sorting, home link, external links and mobile passed.')
if __name__=='__main__':main()
