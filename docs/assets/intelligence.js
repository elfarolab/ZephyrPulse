/* No external JavaScript services. Preferences are stored only in this browser. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = new URL('./', document.currentScript.src); // assets/
  const base = new URL('../', root);
  const node = (tag, text) => {const e=document.createElement(tag); if(text!==undefined) e.textContent=text; return e;};
  const link = (text, href) => {const e=node('a',text); e.href=href; return e;};
  function pattern(value, term) {
    value=String(value??'').toLowerCase(); term=String(term).trim().toLowerCase(); if(!term) return false;
    if(!/[*?\[]/.test(term)) return value.includes(term);
    let regex='^';
    for(let i=0;i<term.length;i++) {
      const c=term[i];
      if(c==='*') regex+='.*'; else if(c==='?') regex+='.';
      else if(c==='[') {
        let end=term.indexOf(']',i+1); if(term[i+1]==='!' || term[i+1]==='^') end=term.indexOf(']',i+2);
        if(end>i+1) {let cls=term.slice(i+1,end); if(cls.startsWith('!')) cls='^'+cls.slice(1); else if(cls.startsWith('^')) cls='\\'+cls; regex+='['+cls.replace(/\\/g,'\\\\')+']'; i=end;}
        else regex+='\\[';
      } else regex+=c.replace(/[\\^$.*+?()[\]{}|]/g,'\\$&');
    }
    try{return new RegExp(regex+'$','s').test(value);}catch(_){return false;}
  }
  const any=(values,terms=[])=>values.some(v=>terms.some(t=>pattern(v,t)));
  function fields(b) {return [b.name,b.full_name,b.folder,...b.socs,...b.targets];}
  function eventMatch(e, prefs, map) {
    const text=[e.subject,e.detail,e.path,e.commit_subject,e.title];
    const boards=(e.boards||[]).map(id=>map.get(id)).filter(Boolean);
    return any([...text,...boards.flatMap(fields)],prefs.boards)||any([...text,...boards.flatMap(b=>[b.vendor,b.vendor_name])],prefs.vendors)||any(text,prefs.peripherals);
  }
  const commit=e=>'https://github.com/zephyrproject-rtos/zephyr/commit/'+e.sha;
  function eventList(target,events,limit=100) {
    target.replaceChildren(node('p',`${events.length} matching events${events.length>limit?` (showing ${limit})`:''}.`));
    const list=node('ul'); for(const e of events.slice(0,limit)) {const li=node('li',`${e.committed.slice(0,10)} · `); li.append(link(e.subject,commit(e)),node('span',` — ${e.kind.replaceAll('_',' ')} · ${e.confidence}`)); list.append(li);} target.append(list);
  }
  async function main(){
    const targets=['pulse-watchlist','pulse-home-watch','pulse-board-filter','pulse-vendor-trends']; if(!targets.some($))return;
    let data,store; try {({data,store}=await window.PulsePreferences.load($('pulse-home-watch')||$('pulse-watchlist')?'data/news-view.json':'intelligence.json'));} catch(_){for(const id of targets){if($(id))$(id).append(node('p','Interactive data unavailable. Static content below remains available.'));} return;}
    const map=new Map(data.boards.map(b=>[b.id,b])); const prefs=store.get();const params=new URLSearchParams(location.search);
    if($('pulse-home-watch')) {const el=$('pulse-home-watch'); const heading=node('h3','Your browser watchlist');const star=node('span');star.className='pulse-icon pulse-i-watch';star.setAttribute('aria-hidden','true');heading.prepend(star, ' ');el.append(heading);const patterns=node('div');patterns.className='pulse-watch-patterns';for(const term of [...prefs.boards,...prefs.vendors,...prefs.peripherals])patterns.append(node('span',term));if(patterns.childElementCount)el.append(patterns); const list=node('div'); el.append(list); const events=data.events.filter(e=>eventMatch(e,prefs,map));if(window.PulseNews)window.PulseNews.render(list,events,map,prefs.home_limit);else eventList(list,events,prefs.home_limit);if($('pulse-home-fallback'))$('pulse-home-fallback').hidden=true;}
    if($('pulse-watchlist')) {
      const el=$('pulse-watchlist'); el.append(node('h2','Personal browser watchlist'),link('Edit preferences',new URL('settings.html',base))); const result=node('div');el.append(result);const events=data.events.filter(e=>eventMatch(e,prefs,map));if(window.PulseNews)window.PulseNews.render(result,events,map,prefs.watch_limit);else eventList(result,events,prefs.watch_limit);if($('pulse-watch-fallback'))$('pulse-watch-fallback').hidden=true;
    }
    if($('pulse-board-filter')){
      const el=$('pulse-board-filter'); const label=node('label','Filter board explorer by name, vendor or SoC'); const input=node('input');input.type='search';input.placeholder='*mcxn*, ra8P1';let vendor=params.get('vendor')||'',subject=params.get('subject')||'';let temporary=!!(vendor||subject);input.value=temporary?'':prefs.explorer_search;label.append(input);el.append(label); const wl=node('label',' Watchlist only');const chk=node('input');chk.type='checkbox';chk.checked=temporary?false:prefs.explorer_watched;wl.prepend(chk);el.append(wl);
      const status=node('p');el.append(status);const active=node('button');active.type='button';active.className='pulse-active-filter';el.append(active);let t=el.nextElementSibling;while(t&&t.tagName!=='TABLE'&&!t.querySelector('table'))t=t.nextElementSibling;t=t&&(t.tagName==='TABLE'?t:t.querySelector('table'));
      if(t){const rows=[...t.querySelectorAll('tbody tr')];const byUrl=new Map(data.boards.map(b=>[new URL(b.url,base).href,b]));const exact=window.PulseTables.exact;
        const refresh=()=>{let n=0;const terms=input.value.split(',').map(s=>s.trim()).filter(Boolean);for(const row of rows){const a=row.querySelector('a');const b=a&&byUrl.get(a.href);const v=b?[...fields(b),b.vendor,b.vendor_name]:[row.textContent];const watched=b&&(any(fields(b),prefs.boards)||any([b.vendor,b.vendor_name],prefs.vendors));const visible=(!vendor||b&&[b.vendor,b.vendor_name].some(x=>exact(x,vendor)))&&(!subject||b&&fields(b).some(x=>exact(x,subject)))&&(!terms.length||any(v,terms))&&(!chk.checked||watched);row.hidden=!visible;if(visible)n++;}status.textContent=`${n} of ${rows.length} boards shown`;active.hidden=!vendor&&!subject;active.textContent=[vendor&&'Vendor: '+vendor,subject&&'Subject: '+subject].filter(Boolean).join(' · ')+' ×';};
        const update=()=>{window.PulseTables.updateParam('vendor',vendor);window.PulseTables.updateParam('subject',subject);refresh();};
        for(const a of t.querySelectorAll('a')){const u=new URL(a.href);if(u.pathname.endsWith('/boards.html')&&u.searchParams.has('subject'))a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();const v=u.searchParams.get('subject');temporary=true;subject=exact(subject,v)?'':v;input.value='';chk.checked=false;update();});}
        active.onclick=()=>{temporary=true;vendor=subject='';input.value='';chk.checked=false;update();};input.addEventListener('input',()=>{if(!temporary)store.update({explorer_search:input.value});refresh();});chk.addEventListener('change',()=>{if(!temporary)store.update({explorer_watched:chk.checked});refresh();});refresh();}
    }
    if($('pulse-vendor-trends')){
      const el=$('pulse-vendor-trends'); const filterMount=$('pulse-vendor-filter'); let vendorFilter=params.get('vendor')||''; const sel=node('select');const label=node('label','Vendor activity by day');label.append(sel);el.append(label); const chart=node('div');el.append(chart);
      for(const v of data.vendors){const opt=node('option',v.vendor);opt.value=v.vendor;sel.append(opt);}
      function draw(){chart.replaceChildren();const v=data.vendors.find(v=>v.vendor===sel.value);if(!v){chart.append(node('p','No attributed activity.'));return;}const end=new Date(data.updated);const start=new Date(data.coverage.cutoff);const points=[];for(let day=new Date(start.toISOString().slice(0,10)+'T00:00:00Z');day<=end;day.setUTCDate(day.getUTCDate()+1)){const d=day.toISOString().slice(0,10);points.push([d,v.daily[d]||0]);}const max=Math.max(1,...points.map(p=>p[1]));chart.append(node('p',`${v.commits} distinct attributed commits · latest ${v.last.slice(0,10)} · ${data.coverage.complete?'complete':'partial'} history`));const bars=node('div');bars.className='pulse-chart';bars.setAttribute('role','img');bars.setAttribute('aria-label','Daily commit count; exact values in table below');for(const [d,n] of points){const bar=node('span');bar.style.height=`${Math.max(n/max*100,1)}%`;bar.title=`${d}: ${n}`;bars.append(bar);}chart.append(bars);const dates=node('div',`${points[0]?.[0]||''}  —  ${points.at(-1)?.[0]||''}`);chart.append(dates);const details=node('details');details.append(node('summary','Daily values (UTC)'));const ul=node('ul');for(const [d,n] of points)ul.append(node('li',`${d}: ${n}`));details.append(ul);chart.append(details);}
      const exact=window.PulseTables.exact;const linked=data.vendors.find(v=>exact(v.vendor,vendorFilter));if(linked)sel.value=linked.vendor;else if(!vendorFilter&&data.vendors.some(v=>v.vendor===prefs.vendor))sel.value=prefs.vendor;
      let table=filterMount?.nextElementSibling;while(table&&table.tagName!=='TABLE'&&!table.querySelector('table'))table=table.nextElementSibling;table=table&&(table.tagName==='TABLE'?table:table.querySelector('table'));
      const status=node('p');const clear=node('button','Show all vendors');clear.type='button';clear.className='pulse-active-filter';if(filterMount)filterMount.append(status,clear);
      function filterTable(){let n=0;const rows=[...(table?.querySelectorAll('tbody tr')||[])];for(const row of rows){const a=row.cells[0]?.querySelector('a');const key=a?new URL(a.href).searchParams.get('vendor'):row.cells[0]?.textContent;row.hidden=!!vendorFilter&&!exact(key,vendorFilter);if(!row.hidden)n++;}status.textContent=vendorFilter?`Vendor: ${vendorFilter} · ${n} of ${rows.length} vendors shown`:`${rows.length} vendors shown`;clear.hidden=!vendorFilter;if(vendorFilter&&!data.vendors.some(v=>exact(v.vendor,vendorFilter))){chart.replaceChildren(node('p','No attributed activity for this vendor in the retained history.'));}else draw();}
      clear.onclick=()=>{vendorFilter='';window.PulseTables.updateParam('vendor','');filterTable();};sel.addEventListener('change',()=>{if(vendorFilter){vendorFilter=sel.value;window.PulseTables.updateParam('vendor',vendorFilter);}else store.update({vendor:sel.value});filterTable();});filterTable();
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main);else main();
})();
