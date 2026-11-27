"""Exercise the shared timestamp script without a live HTTP server."""
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]

def main():
    with sync_playwright() as pw:
        args={'headless':True,'args':['--no-sandbox']}
        if shutil.which('chromium'): args['executable_path']=shutil.which('chromium')
        browser=pw.chromium.launch(**args); page=browser.new_page();page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for available in (True,False):
            page.goto('about:blank')
            page.set_content('<main><p>Updated <strong data-pulse-updated>—</strong> · rolling 72 hours · upstream Git</p><span data-pulse-pr-updated>—</span></main>')
            page.evaluate('''available=>{
                Object.defineProperty(document,'currentScript',{configurable:true,get:()=>({src:'https://fixture.invalid/assets/theme-zensical.js?pulse_v=123'})});
                window.fetch=async (url,options)=>{window.requested=String(url);window.cacheMode=options.cache;
                    if(!available)throw Error('offline');return {ok:true,json:async()=>({updated:'2026-11-27T17:20:53+00:00',pr_updated:'2026-11-27T16:00:00+00:00'})};};
            }''',available)
            page.add_script_tag(path=ROOT/'docs/assets/theme-zensical.js')
            if available:
                expect(page.locator('[data-pulse-updated]')).to_have_text('2026-11-27 17:20 UTC')
                expect(page.locator('[data-pulse-pr-updated]')).to_have_text('2026-11-27 16:00 UTC')
            else:
                expect(page.locator('[data-pulse-updated]')).to_have_attribute('title','Collection timestamp unavailable')
                expect(page.locator('[data-pulse-updated]')).to_have_text('—')
            assert page.evaluate('window.requested')=='https://fixture.invalid/data/status.json'
            assert page.evaluate('window.cacheMode')=='no-cache'
        assert not errors,errors
        browser.close()
    print('Shared status timestamp, asset-relative URL and unavailable fallback passed.')
if __name__=='__main__':main()
