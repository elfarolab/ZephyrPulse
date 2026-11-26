/* Optional presentation bridge. The preference store does not depend on a theme. */
((global)=>{
  let original=null;
  global.PulseTheme={apply(value){
    if(!document.body)return;
    if(original===null)original=document.body.dataset.mdColorScheme||'default';
    const scheme=value==='dark'?'slate':value==='light'?'default':original;
    const input=[...document.querySelectorAll('input[data-md-color-scheme]')].find(x=>x.dataset.mdColorScheme===scheme);
    if(input&&!input.checked)input.click();
    document.body.dataset.mdColorScheme=scheme;
  }};
})(window);

/* Theme-only tab decoration. The application does not depend on these selectors. */
(()=>{
  const icons={'Overview':'overview','Hardware':'cpu','Explore':'search','Intelligence':'intelligence','More news':'news','Personal':'settings'};
  function decorate(){for(const link of document.querySelectorAll('.md-tabs__link')){const name=link.textContent.trim();if(!Object.hasOwn(icons,name)||link.querySelector('.pulse-icon'))continue;const icon=document.createElement('span');icon.className='pulse-icon pulse-i-'+icons[name];icon.setAttribute('aria-hidden','true');link.prepend(icon);}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',decorate);else decorate();
})();
