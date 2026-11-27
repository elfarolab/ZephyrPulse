/* Portable news table: no framework, all rows and evidence in the static HTML. */
(()=>{'use strict';
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const labels={board_feature:'Board capability changes',board_candidate:'Possible board support',board:'New boards',board_change:'Board maintenance',sensor:'Sensors',driver:'Drivers',soc:'SoCs',dts:'Devicetree',docs:'Documentation',other:'Other changes'};
const icons={board_feature:'capability',board_candidate:'candidate',board:'board',board_change:'board',sensor:'sensor',driver:'driver',soc:'cpu',dts:'dts',docs:'docs',other:'news'};
const glyph=name=>{const e=node('span',undefined,'pulse-icon pulse-i-'+name);e.setAttribute('aria-hidden','true');return e;};
const upstream='https://github.com/zephyrproject-rtos/zephyr';
const fold=v=>String(v??'').toLowerCase();
const cmp=(a,b)=>a.localeCompare(b,undefined,{numeric:true,sensitivity:'base'});
let serial=0;
function init(root){
  if(root.dataset.pulseReady)return;
  const body=root.querySelector('tbody');if(!body)return;
  const pairs=[...body.querySelectorAll('tr.pulse-news-row')].map((row,i)=>({row,detail:row.nextElementSibling,i})).filter(p=>p.detail?.classList.contains('pulse-news-detail'));
  if(!pairs.length)return;
  root.dataset.pulseReady='true';
  const uid='pulse-news-'+(++serial); const controls=node('div',undefined,'pulse-news-controls');
  function field(title,el){const l=node('label',title);el.setAttribute('aria-label',title);l.append(el);controls.append(l);return el;}
  const query=field('Filter news',node('input'));query.type='search';query.placeholder='Board, vendor, headline, SHA…';
  const category=field('Category',node('select'));category.append(new Option('All categories',''));for(const k of Object.keys(labels))if(pairs.some(p=>p.row.dataset.kind===k))category.append(new Option(labels[k],k));
  const changeType=field('Change type',node('select'));changeType.append(new Option('All change types',''));for(const t of [...new Set(pairs.map(p=>p.row.dataset.changeType||'Unknown'))].sort(cmp))changeType.append(new Option(t,t));
  const sort=field('Sort by',node('select'));for(const [v,t] of [['newest','Newest first'],['oldest','Oldest first'],['category','Category'],['change_type','Change type'],['subject','Subject / target'],['vendor','Vendor association'],['confidence','Confidence'],['headline','Headline'],['release','Release'],['commit','Commit']])sort.append(new Option(t,v));
  const size=field('Rows per page',node('select'));for(const n of [25,50,100,200])size.append(new Option(n,n));size.append(new Option('All','all'));size.value=String(root.dataset.pulseNews||100);
  const toggleAll=node('button','Expand page');toggleAll.type='button';controls.append(toggleAll);
  root.prepend(controls);
  const nav=node('div',undefined,'pulse-news-pagination');const prev=node('button','Previous'),next=node('button','Next'),status=node('span');prev.type=next.type='button';status.setAttribute('aria-live','polite');nav.append(prev,status,next);root.append(nav);
  let page=0, shown=[], headerSort=null; const sorter=window.PulseTables?.headers(root.querySelector('table'),(index,dir)=>{headerSort={index,dir};if(![...sort.options].some(o=>o.value==='column'))sort.append(new Option('Selected column','column'));sort.value='column';page=0;draw();},{skip:[0],current:{index:1,dir:-1}});
  const preview=root.dataset.pulsePreview==='true';
  const initialSubject=new URLSearchParams(location.search).get('subject');
  let subjectFilter=preview?'':(initialSubject||'');
  const active=node('button','');active.type='button';active.className='pulse-active-filter';active.hidden=true;controls.append(active);
  function setSubject(value){subjectFilter=value;page=0;
    if(/^(?:https?:)$/.test(location.protocol)&&Object.keys(labels).some(k=>location.pathname.endsWith('/'+k+'.html'))){const url=new URL(location.href);if(value)url.searchParams.set('subject',value);else url.searchParams.delete('subject');history.replaceState(null,'',url);}
    draw();}
  active.onclick=()=>setSubject('');
  function expand(p,on){p.open=on;p.detail.hidden=!on||p.row.hidden;p.button.setAttribute('aria-expanded',String(on));p.button.firstElementChild.textContent=on?'▾':'▸';}
  for(const p of pairs){p.button=p.row.querySelector('button');p.detail.id=uid+'-'+p.i;p.button.setAttribute('aria-controls',p.detail.id);p.text=fold(p.row.textContent+' '+p.detail.textContent+' '+p.row.dataset.vendor);p.subject=p.row.querySelector('.pulse-news-col-2').textContent.trim();
    const subjectLinks=[...p.row.querySelectorAll('.pulse-subject-filter'),...p.detail.querySelectorAll('.pulse-subject-filter')];if(!preview)for(const subjectLink of subjectLinks)subjectLink.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();setSubject(fold(subjectFilter)===fold(p.subject)?'':p.subject);});expand(p,false);p.button.addEventListener('click',()=>{expand(p,!p.open);updateToggle();});p.row.addEventListener('click',e=>{if(e.target.closest('button,a,input,select')||String(window.getSelection()).length)return;expand(p,!p.open);updateToggle();});}
  function updateToggle(){toggleAll.textContent=shown.length&&shown.every(p=>p.open)?'Collapse page':'Expand page';toggleAll.disabled=!shown.length;}
  function draw(){
    const terms=fold(query.value).trim().split(/\s+/).filter(Boolean);const k=category.value;
    const result=pairs.filter(p=>(!k||p.row.dataset.kind===k)&&(!changeType.value||(p.row.dataset.changeType||'Unknown')===changeType.value)&&(!subjectFilter||fold(p.subject)===fold(subjectFilter))&&terms.every(t=>p.text.includes(t)));
    active.hidden=!subjectFilter;active.textContent='Subject: '+subjectFilter+' ×';active.setAttribute('aria-label','Clear subject filter');
    for(const p of pairs){for(const a of [...p.row.querySelectorAll('.pulse-subject-filter'),...p.detail.querySelectorAll('.pulse-subject-filter')]){a.classList.toggle('pulse-filter-active',!!subjectFilter&&fold(p.subject)===fold(subjectFilter));a.title=subjectFilter&&fold(p.subject)===fold(subjectFilter)?'Remove subject filter':'Filter by this subject';}}
    const cell=(p,n)=>p.row.querySelector('.pulse-news-col-'+n)?.textContent.trim()||'';
    result.sort((a,b)=>{if(headerSort){const n=headerSort.index-1;return headerSort.dir*cmp(n===0?a.row.dataset.time:cell(a,n),n===0?b.row.dataset.time:cell(b,n))||a.i-b.i;}let r=0;switch(sort.value){case 'change_type':r=cmp(a.row.dataset.changeType||'Unknown',b.row.dataset.changeType||'Unknown');break;case 'oldest':r=cmp(a.row.dataset.time,b.row.dataset.time);break;case 'category':r=cmp(cell(a,1),cell(b,1));break;case 'subject':r=cmp(cell(a,2),cell(b,2));break;case 'vendor':r=cmp(a.row.dataset.vendor||'\uffff',b.row.dataset.vendor||'\uffff');break;case 'confidence':r=cmp(a.row.dataset.confidence,b.row.dataset.confidence);break;case 'headline':r=cmp(cell(a,3),cell(b,3));break;case 'release':r=cmp(cell(a,5),cell(b,5));break;case 'commit':r=cmp(cell(a,6),cell(b,6));break;default:r=cmp(b.row.dataset.time,a.row.dataset.time);}return r||a.i-b.i;});
    const count=size.value==='all'?Math.max(1,result.length):Number(size.value)||100;const pages=Math.max(1,Math.ceil(result.length/count));page=Math.max(0,Math.min(page,pages-1));shown=result.slice(page*count,(page+1)*count);const visible=new Set(shown),matched=new Set(result);
    const frag=document.createDocumentFragment();for(const p of [...result,...pairs.filter(p=>!matched.has(p))]){p.row.hidden=!visible.has(p);p.detail.hidden=p.row.hidden||!p.open;frag.append(p.row,p.detail);}body.append(frag);
    status.textContent=result.length?`${page*count+1}–${Math.min(result.length,(page+1)*count)} of ${result.length} events · ${pairs.length} total`:`No matches · ${pairs.length} total`;
    prev.disabled=page===0;next.disabled=page+1>=pages;updateToggle();
  }
  for(const e of [query,category,changeType,sort,size])e.addEventListener(e===query?'input':'change',()=>{if(e===sort&&sort.value!=='column'){headerSort=null;sort.querySelector('option[value=column]')?.remove();const mapping={newest:[1,-1],oldest:[1,1],category:[2,1],subject:[3,1],confidence:[5,1],headline:[4,1],release:[6,1],commit:[7,1]};const m=mapping[sort.value];sorter?.show(m?.[0],m?.[1]);}page=0;draw();});
  prev.onclick=()=>{page--;draw();root.scrollIntoView({block:'start'});};next.onclick=()=>{page++;draw();root.scrollIntoView({block:'start'});};toggleAll.onclick=()=>{const on=!shown.every(p=>p.open);shown.forEach(p=>expand(p,on));updateToggle();};draw();
}
function render(target,events,boards,limit=100,relatedEvents=events){
  target.replaceChildren(node('p',`${events.length} matching events${events.length>limit?` (showing ${limit})`:''}.`));if(!events.length)return;
  const root=node('div',undefined,'pulse-news-table');root.dataset.pulseNews='100';const scroll=node('div',undefined,'pulse-news-scroll'),table=node('table',undefined,'pulse-news-list'),head=node('thead'),hr=node('tr'),body=node('tbody');
  const cols=node('colgroup');cols.append(node('col',undefined,'pulse-news-expand-col'));const dataCols=node('col');dataCols.span=7;cols.append(dataCols);
  for(const label of ['Details','UTC date / time','Category','Subject / target','Headline','Confidence','Release','Commit']){const th=node('th',label);th.scope='col';if(label==='Details'){th.className='pulse-news-expand';th.replaceChildren(node('span',label,'pulse-sr-only'));}hr.append(th);}head.append(hr);table.append(cols,head,body);scroll.append(table);root.append(scroll);target.append(root);
  const relatedBySubject=new Map();for(const e of relatedEvents){const key=fold(e.subject);if(!relatedBySubject.has(key))relatedBySubject.set(key,new Set());if(Object.hasOwn(labels,e.kind))relatedBySubject.get(key).add(e.kind);}
  for(const e of events.slice(0,limit)){
    const kind=Object.hasOwn(labels,e.kind)?e.kind:'other',subject=String(e.subject||''),headline=e.commit_subject||subject,confidence=String(e.confidence||'unknown'),stamp=String(e.committed||'').slice(0,16).replace('T',' '),release=e.release?.first_release||(e.release?.status==='main_only'?'Not in tracked releases':'Unknown');
    const linked=(e.boards||[]).map(id=>boards.get(id)).filter(Boolean),profile=linked.find(b=>b.url===e.board_profile_url&&/^boards\/[\w.-]+\.html$/.test(b.url||'')),vendors=linked.map(b=>b.vendor_name||b.vendor||'').join(' ');
    const row=node('tr',undefined,'pulse-news-row pulse-cat-'+kind);Object.assign(row.dataset,{kind,changeType:e.change_type||'Unknown',time:e.committed||'',vendor:vendors,confidence});const td=node('td',undefined,'pulse-news-expand'),btn=node('button',undefined,'pulse-news-toggle');btn.type='button';btn.setAttribute('aria-label','Details for '+subject);const arrow=node('span','▸');arrow.setAttribute('aria-hidden','true');btn.append(arrow);td.append(btn);row.append(td);
    [stamp,labels[kind],subject,headline,confidence,release,String(e.sha||'').slice(0,10)].forEach((value,i)=>{const cell=node('td',value,'pulse-news-col-'+i);cell.title=value;if(i===1||i===2){const a=node('a',value,i===1?'pulse-category-link':'pulse-subject-filter');a.href=kind+'.html'+(i===2?'?subject='+encodeURIComponent(subject):'');if(i===1)a.prepend(glyph(icons[kind]),' ');else if(profile){a.className='pulse-board-profile-link';a.href=profile.url;a.title='Open board profile';}else a.dataset.subject=subject;cell.replaceChildren(a);}row.append(cell);});
    const detail=node('tr',undefined,'pulse-news-detail'),cell=node('td'),panel=node('article',undefined,'pulse-news-detail-panel');cell.colSpan=8;panel.append(node('strong',subject),node('p',headline),node('p',e.detail||''),node('p','Change type: '+(e.change_type||'Unknown')),node('p',`${stamp} UTC · ${labels[kind]} · ${confidence} · ${release} (exact commit inclusion)`));if(profile){const f=node('p','Subject filter: '),a=node('a',subject,'pulse-subject-filter');a.dataset.subject=subject;a.href=kind+'.html?subject='+encodeURIComponent(subject);f.append(a);panel.append(f);}if(vendors)panel.append(node('p','Vendor association: '+vendors));if(e.path)panel.append(node('p','Source: '+e.path+(e.source_revision&&e.source_revision!==e.sha?' (before removal)':'')));
    const links=node('p',undefined,'pulse-news-links');const link=(text,url)=>{const a=node('a',text);a.href=url;return a;};const sha=encodeURIComponent(e.sha||'');links.append(link('Commit '+e.sha,upstream+'/commit/'+sha));if(e.path)links.append(' · ',link('Source file',upstream+'/blob/'+encodeURIComponent(e.source_revision||e.sha||'')+'/'+e.path.split('/').map(encodeURIComponent).join('/')));for(const b of linked)if(/^boards\/[\w.-]+\.html$/.test(b.url||''))links.append(' · ',link(b.name,b.url));const related=[...(relatedBySubject.get(fold(subject))||[])].filter(k=>k!==kind);for(const k of related)links.append(' · ',link(labels[k],k+'.html?subject='+encodeURIComponent(subject)));links.append(' · ',link('Related hardware / news','hardware-search.html?subject='+encodeURIComponent(subject)));panel.append(links);cell.append(panel);detail.append(cell);body.append(row,detail);
  }
  init(root);
}
window.PulseNews={init,render};async function start(){document.querySelectorAll('[data-pulse-news]').forEach(init);const mounts=[...document.querySelectorAll('[data-pulse-category]')];if(!mounts.length)return;try{const {data}=await window.PulsePreferences.load('data/news-view.json');const boards=new Map(data.boards.map(b=>[b.id,b]));for(const m of mounts){const items=data.events.filter(e=>e.kind===m.dataset.pulseCategory);render(m,items,boards,items.length,data.events);}}catch(e){for(const m of mounts)m.textContent='News unavailable. Use the raw JSON or All commits link below, or refresh.';}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
