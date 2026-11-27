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
    const list=node('ul'); for(const e of events.slice(0,limit)) {const li=node('li',`${e.committed.slice(0,10)} · `);li.dataset.commitTime=e.committed; li.append(link(e.subject,/^boards\/[\w.-]+\.html$/.test(e.board_profile_url||'')?e.board_profile_url:commit(e)),node('span',` — ${e.kind.replaceAll('_',' ')} · ${e.confidence}`)); list.append(li);} target.append(list);
  }
  async function main(){
    const targets=['pulse-watchlist','pulse-home-watch','pulse-board-filter','pulse-vendor-trends']; if(!targets.some($))return;
    let data,store; try {({data,store}=await window.PulsePreferences.load($('pulse-home-watch')||$('pulse-watchlist')?'data/news-view.json':'intelligence.json'));} catch(_){for(const id of targets){if($(id))$(id).append(node('p','Interactive data unavailable. Static content below remains available.'));} return;}
    const map=new Map(data.boards.map(b=>[b.id,b])); const prefs=store.get();const params=new URLSearchParams(location.search);
    if($('pulse-home-watch')) {const el=$('pulse-home-watch'); const heading=node('h3','Your browser watchlist');const star=node('span');star.className='pulse-icon pulse-i-watch';star.setAttribute('aria-hidden','true');heading.prepend(star, ' ');el.append(heading);const patterns=node('div');patterns.className='pulse-watch-patterns';for(const term of [...prefs.boards,...prefs.vendors,...prefs.peripherals]){const chip=node('span',term);chip.dataset.testid='watch-tag';patterns.append(chip);}if(patterns.childElementCount)el.append(patterns); const list=node('div'); el.append(list); const events=data.events.filter(e=>eventMatch(e,prefs,map));if(window.PulseNews)window.PulseNews.render(list,events,map,prefs.home_limit);else eventList(list,events,prefs.home_limit);if($('pulse-home-fallback'))$('pulse-home-fallback').hidden=true;}
    if($('pulse-watchlist')) {
      const el=$('pulse-watchlist'); el.append(node('h2','Personal browser watchlist'),link('Edit preferences',new URL('settings.html',base))); const result=node('div');el.append(result);const events=data.events.filter(e=>eventMatch(e,prefs,map));if(window.PulseNews)window.PulseNews.render(result,events,map,prefs.watch_limit);else eventList(result,events,prefs.watch_limit);if($('pulse-watch-fallback'))$('pulse-watch-fallback').hidden=true;
    }
    if($('pulse-board-filter')){
      const el=$('pulse-board-filter'); const label=node('label','Filter board explorer by name, vendor or SoC'); const input=node('input');input.type='search';input.placeholder='*mcxn*, ra8P1';let vendor=params.get('vendor')||'',subject=params.get('subject')||'';let temporary=!!(vendor||subject);input.value=temporary?'':prefs.explorer_search;label.append(input);el.append(label); const wl=node('label',' Watchlist only');const chk=node('input');chk.type='checkbox';chk.checked=temporary?false:prefs.explorer_watched;wl.prepend(chk);el.append(wl);
      const status=node('p');el.append(status);const active=node('button');active.type='button';active.className='pulse-active-filter';el.append(active);let t=el.nextElementSibling;while(t&&t.tagName!=='TABLE'&&!t.querySelector('table'))t=t.nextElementSibling;t=t&&(t.tagName==='TABLE'?t:t.querySelector('table'));
      if(t){const rows=[...t.querySelectorAll('tbody tr')];const byUrl=new Map(data.boards.map(b=>[new URL(b.url,base).href,b]));const exact=window.PulseTables.exact;
        // Reuse the static board links and evidence; leave the flat table available if JS is disabled.
        const table=node('table');table.className='pulse-vendor-explorer';table.dataset.pulseManaged='true';
        const head=table.createTHead().insertRow();for(const title of ['Details','Vendor','Boards','Last detected milestone']){const th=node('th',title);th.scope='col';head.append(th);}head.cells[0].className='pulse-news-expand';head.cells[0].replaceChildren(node('span','Details'));head.cells[0].firstChild.className='pulse-sr-only';
        const body=table.createTBody(),groups=new Map(),boardRows=[];
        for(const row of rows){const a=row.querySelector('a'),b=a&&byUrl.get(a.href);const key=b?.vendor||row.cells[1]?.textContent.trim()||'Unknown';let g=groups.get(key);
          if(!g){g={key,name:b?.vendor_name||row.cells[1]?.textContent.trim()||key,items:[],open:false};groups.set(key,g);}g.items.push({row,b});boardRows.push({row,b});}
        const allToggle=node('button','Expand all vendors');allToggle.type='button';allToggle.className='pulse-active-filter';el.append(allToggle);
        let sort={index:1,dir:1};const ordered=[...groups.values()];
        for(const g of ordered){const row=node('tr'),detail=node('tr');row.className='pulse-vendor-group';detail.className='pulse-vendor-detail';g.row=row;g.detail=detail;
          const expand=row.insertCell();expand.className='pulse-news-expand';const toggle=node('button');toggle.type='button';toggle.className='pulse-news-toggle';toggle.setAttribute('aria-label','Boards for '+g.name);const arrow=node('span','▸');arrow.setAttribute('aria-hidden','true');toggle.append(arrow);expand.append(toggle);
          const name=row.insertCell(),nameToggle=node('button',g.name);nameToggle.type='button';nameToggle.className='pulse-commit-expand';name.append(nameToggle);const activity=g.items[0].row.cells[1]?.querySelector('a');if(activity){activity.textContent='Activity';activity.title='Vendor activity: '+g.name;activity.classList.add('pulse-vendor-activity');name.append(' ',activity);}const count=row.insertCell(),latest=row.insertCell();g.count=count;g.latest=latest;
          const panel=detail.insertCell();panel.colSpan=4;const inner=node('table');inner.className='pulse-vendor-boards';inner.dataset.pulseManaged='true';const ih=inner.createTHead().insertRow();for(const th of [...t.tHead.rows[0].cells].filter((_,i)=>i!==1)){const h=node('th',th.querySelector('button')?.title.replace(/^Sort by /,'')||th.textContent.trim());h.scope='col';ih.append(h);}const ib=inner.createTBody();
          for(const item of g.items){item.row.deleteCell(1);ib.append(item.row);}
          window.PulseTables.headers(inner,(i,dir)=>{for(const r of window.PulseTables.sortRows([...ib.rows],r=>r.cells[i]?.textContent,dir))ib.append(r);});panel.append(inner);body.append(row,detail);
          g.show=()=>{detail.hidden=row.hidden||!g.open;toggle.setAttribute('aria-expanded',String(g.open));nameToggle.setAttribute('aria-expanded',String(g.open));arrow.textContent=g.open?'▾':'▸';};toggle.onclick=nameToggle.onclick=()=>{g.open=!g.open;g.show();syncToggle();};g.show();}
        function syncToggle(){const visible=ordered.filter(g=>!g.row.hidden);allToggle.textContent=visible.length&&visible.every(g=>g.open)?'Collapse all vendors':'Expand all vendors';allToggle.disabled=!visible.length;}
        function reorder(){const sorted=window.PulseTables.sortRows(ordered,g=>sort.index===1?g.name:sort.index===2?g.count.dataset.sortValue:g.latest.textContent,sort.dir);for(const g of sorted)body.append(g.row,g.detail);}
        window.PulseTables.headers(table,(index,dir)=>{sort={index,dir};reorder();},{skip:[0],current:{index:1,dir:1}});
        const refresh=()=>{let n=0,vendors=0;const terms=input.value.split(',').map(s=>s.trim()).filter(Boolean),filtering=!!(vendor||subject||terms.length||chk.checked);for(const g of ordered){let matched=0;const dates=[];for(const {row,b} of g.items){const v=b?[...fields(b),b.vendor,b.vendor_name]:[row.textContent,g.name,g.key];const watched=b&&(any(fields(b),prefs.boards)||any([b.vendor,b.vendor_name],prefs.vendors));const visible=(!vendor||b&&[b.vendor,b.vendor_name].some(x=>exact(x,vendor)))&&(!subject||b&&fields(b).some(x=>exact(x,subject)))&&(!terms.length||any(v,terms))&&(!chk.checked||watched);row.hidden=!visible;if(visible){matched++;n++;const date=row.cells[2]?.textContent.trim();if(date&&date!=='—')dates.push(date);}}g.row.hidden=!matched;if(matched)vendors++;g.count.textContent=matched===g.items.length?String(matched):`${matched} / ${g.items.length}`;g.count.dataset.sortValue=String(matched);g.latest.textContent=dates.sort().at(-1)||'—';g.open=filtering&&matched>0;g.show();}status.textContent=`${n} of ${boardRows.length} boards shown · ${vendors} of ${groups.size} vendors`;active.hidden=!vendor&&!subject;active.textContent=[vendor&&'Vendor: '+vendor,subject&&'Subject: '+subject].filter(Boolean).join(' · ')+' ×';reorder();syncToggle();};
        const update=()=>{window.PulseTables.updateParam('vendor',vendor);window.PulseTables.updateParam('subject',subject);refresh();};
        for(const a of table.querySelectorAll('a')){const u=new URL(a.href);if(u.pathname.endsWith('/boards.html')&&u.searchParams.has('subject'))a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();const v=u.searchParams.get('subject');temporary=true;subject=exact(subject,v)?'':v;input.value='';chk.checked=false;update();});}
        allToggle.onclick=()=>{const visible=ordered.filter(g=>!g.row.hidden);const open=!visible.every(g=>g.open);for(const g of visible){g.open=open;g.show();}syncToggle();};
        active.onclick=()=>{temporary=true;vendor=subject='';input.value='';chk.checked=false;update();};input.addEventListener('input',()=>{if(!temporary)store.update({explorer_search:input.value});refresh();});chk.addEventListener('change',()=>{if(!temporary)store.update({explorer_watched:chk.checked});refresh();});const wrapper=node('div');wrapper.className='pulse-vendor-explorer-scroll';t.replaceWith(wrapper);wrapper.append(table);refresh();}

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
