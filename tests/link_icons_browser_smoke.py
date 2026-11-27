"""Exercise the shared link decoration on static and asynchronously inserted links."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def main():
    with TemporaryDirectory() as tmp, sync_playwright() as pw:
        fixture=Path(tmp)/'board.html'
        fixture.write_text('''<html><head><base href="https://fixture.invalid/"></head><body><main class="md-content">
        <a id="source" href="https://github.com/zephyrproject-rtos/zephyr/tree/main/boards/kit">Board source</a>
        <a id="board" href="boards/kit.html">kit</a>
        <a id="soc" href="boards.html?subject=chip">chip</a>
        <a id="vendor" href="vendors.html?vendor=test">Test vendor</a>
        <a id="doc" href="https://docs.zephyrproject.org/latest/boards/kit.html">Official docs</a>
        <a id="feed" href="feed.xml">RSS</a><a id="json" href="events.json">JSON</a>
        <a id="compare" href="compare.html?board=kit">Compare</a>
        <a id="image" href="data/board-images/kit.png"><img alt="kit"></a>
        <a id="anchor" href="#foo">Heading</a>
        <a id="existing" href="board.html"><span class="pulse-icon pulse-i-board" aria-hidden="true"></span>Existing</a>
        <div id="dynamic"></div></main></body></html>''')
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'):args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args);page=browser.new_page();page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(fixture.read_text());page.add_style_tag(path=ROOT/'docs/assets/pulse.css');page.add_script_tag(path=ROOT/'docs/assets/theme-zensical.js')
        expected={'source':'github','board':'board','soc':'cpu','vendor':'intelligence','doc':'docs','feed':'rss','json':'json','compare':'compare'}
        for name,kind in expected.items():
            icon=page.locator(f'#{name} > .pulse-i-{kind}');icon.wait_for();assert icon.get_attribute('aria-hidden')=='true';assert icon.evaluate("el=>getComputedStyle(el).maskImage!=='none'")
        assert page.get_by_role('link',name='Board source',exact=True).count()==1
        assert page.locator('#image .pulse-icon,#anchor .pulse-icon').count()==0
        assert page.locator('#existing .pulse-icon').count()==1
        page.evaluate('''()=>{const a=document.createElement('a');a.id='new';a.href='https://github.com/zephyrproject-rtos/zephyr/pull/42';a.textContent='PR';a.addEventListener('click',e=>{e.preventDefault();a.dataset.clicked='yes'});document.querySelector('#dynamic').append(a)}''')
        page.locator('#new .pulse-i-pr').wait_for();page.locator('#new').click();assert page.locator('#new').get_attribute('data-clicked')=='yes'
        page.evaluate("document.querySelector('#new').href='compare.html'")
        page.locator('#new .pulse-i-compare').wait_for();assert page.locator('#new .pulse-icon').count()==1
        page.evaluate("document.querySelector('#new').textContent='Updated'")
        page.locator('#new .pulse-i-compare').wait_for();assert page.get_by_role('link',name='Updated',exact=True).count()==1
        page.evaluate("PulseLinkIcons.scan(document.querySelector('main'))")
        assert page.locator('#new .pulse-icon').count()==1
        assert not errors,errors
        browser.close()
    print('Shared static/dynamic link icons, semantics, accessibility and event preservation passed.')
if __name__=='__main__':main()
