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

/* Shared semantic link icons for static Markdown and browser-generated content.
 * Preserve link text, destinations, event handlers and existing category icons. */
((global)=>{
  const categories={board_feature:'capability',board_candidate:'candidate',board:'board',board_change:'board',sensor:'sensor',driver:'driver',soc:'cpu',dts:'dts',dt_bindings:'bindings',subsys:'subsys',samples:'samples',tests:'tests',manifest:'manifest',docs:'docs',other:'news',all:'news'};
  const scope='.md-content, .pulse-universal-dialog, .md-sidebar--primary';
  function kind(a){
    const raw=a.getAttribute('href')||'';
    if(!raw||raw.startsWith('#'))return null;
    let url;try{url=new URL(raw,document.baseURI);}catch(_){return null;}
    if(!['http:','https:','file:'].includes(url.protocol))return null;
    const path=url.pathname.toLowerCase(), text=a.textContent.trim().toLowerCase();
    if(a.classList.contains('pulse-subject-filter')||a.hasAttribute('data-subject'))return 'filter';
    if(url.hostname==='github.com'){
      if(/\/commit\//.test(path))return 'commit';
      if(/\/commits\//.test(path))return 'history';
      if(/\/pull\//.test(path))return 'pr';
      if(/\/releases(?:\/|$)/.test(path))return 'release';
      if(/image source/.test(text))return 'image';
      return 'github';
    }
    if(url.hostname==='docs.zephyrproject.org')return 'docs';
    if(url.origin!==new URL(document.baseURI).origin)return 'external';
    if(/\.(?:png|webp|jpe?g|gif|svg)$/.test(path))return 'image';
    if(/\.xml$/.test(path))return 'rss';
    if(/\.json$/.test(path))return 'json';
    if(/\/boards\/[^/]+\.(?:html|md)$/.test(path))return 'board';
    const page=(path.split('/').pop()||'index').replace(/\.(?:html|md)$/,'');
    if(page==='boards')return url.searchParams.has('subject')?'cpu':url.searchParams.has('vendor')?'board':'overview';
    if(page==='compare')return 'compare';
    if(page==='vendors')return 'intelligence';
    if(page==='hardware-search')return 'search';
    if(page==='settings')return 'settings';
    if(page==='watchlist')return 'watch';
    if(page==='upcoming')return 'pr';
    if(page==='releases')return 'release';
    if(page==='index')return 'overview';
    return categories[page]||'external';
  }
  function decorate(a){
    if(!a.matches('a[href]')||a.matches('.headerlink, .md-nav__link--index')||a.querySelector('img, svg, .pulse-icon:not(.pulse-auto-link-icon)')||!a.textContent.trim())return;
    const type=kind(a), old=a.querySelector(':scope > .pulse-auto-link-icon');
    if(!type){old?.remove();return;}
    const cls='pulse-icon pulse-auto-link-icon pulse-i-'+type;
    if(old){if(old.className!==cls)old.className=cls;return;}
    const icon=document.createElement('span');icon.className=cls;icon.setAttribute('aria-hidden','true');a.prepend(icon);
  }
  function scan(root){if(root.nodeType!==1)return;if(root.matches('a[href]'))decorate(root);root.querySelectorAll('a[href]').forEach(decorate);}
  function start(){
    document.querySelectorAll(scope).forEach(scan);
    // Observe asynchronous table/filter redraws without rescanning the entire page.
    const observer=new MutationObserver(records=>{for(const r of records){
      const target=r.target.nodeType===1?r.target:r.target.parentElement;
      if(target?.closest(scope)){const a=target.closest('a[href]');if(a)decorate(a);}
      if(r.type==='childList')for(const el of r.addedNodes){if(el.nodeType!==1)continue;if(el.closest(scope))scan(el);else el.querySelectorAll(scope).forEach(scan);}
    }});
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['href']});
  }
  global.PulseLinkIcons={kind,decorate,scan};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})(window);

/* Home navigation and external-link policy, independent of semantic icons.
 * Handle the repository header, footer, and newly rendered application links. */
(()=>{
  const script=document.currentScript;
  const home=script?.src?new URL('../index.html',script.src).href:null;
  const managed=new WeakMap();
  function link(a){
    const raw=a.getAttribute('href');let external=false;
    if(raw){try{const u=new URL(raw,document.baseURI);external=['http:','https:'].includes(u.protocol)&&u.origin!==new URL(document.baseURI).origin;}catch(_){}}
    if(external){
      if(!managed.has(a))managed.set(a,{target:a.getAttribute('target'),rel:a.getAttribute('rel')});
      a.target='_blank';a.relList.add('noopener','noreferrer');
    }else if(managed.has(a)){
      const prior=managed.get(a);for(const key of ['target','rel']){if(prior[key]===null)a.removeAttribute(key);else a.setAttribute(key,prior[key]);}managed.delete(a);
    }
  }
  function scan(root){if(root.nodeType!==1&&root.nodeType!==9)return;if(root.matches?.('a[href]'))link(root);root.querySelectorAll('a[href]').forEach(link);}
  function title(){
    const topic=document.querySelector('.md-header__title .md-header__topic');
    const text=topic?.querySelector('.md-ellipsis')||topic;
    if(!topic||!text)return;
    const container=topic.closest('.md-header__title');
    container.classList.add('pulse-brand-header');topic.classList.add('pulse-brand-topic');
    if(text.querySelector('.pulse-home-title')||text.matches('.pulse-home-title'))return;
    const logo=document.querySelector('a.md-header__button.md-logo[href]');
    const href=home||logo?.href;if(!href)return;
    const a=document.createElement('a');a.className='pulse-home-title';a.href=href;a.setAttribute('aria-label','Zephyr Pulse home');a.title='Zephyr Pulse home';
    a.textContent='Zephyr Pulse';text.replaceChildren(a);
  }
  function start(){title();scan(document);new MutationObserver(records=>{for(const r of records){if(r.type==='attributes'&&r.target.matches('a'))link(r.target);else for(const el of r.addedNodes)scan(el);}}).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['href']});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
