/* Portable news table: no framework, all rows and evidence in the static HTML. */
(()=>{'use strict';
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const labels={board_feature:'Board capability changes',board_candidate:'Possible board support',board:'New boards',board_change:'Board maintenance',sensor:'Sensors',driver:'Drivers',soc:'SoCs',dts:'Devicetree',docs:'Documentation',other:'Other changes'};
const icons={board_feature:'capability',board_candidate:'candidate',board:'board',board_change:'board',sensor:'sensor',driver:'driver',soc:'cpu',dts:'dts',docs:'docs',other:'news'};
const glyph=name=>{const e=node('span',undefined,'pulse-icon pulse-i-'+name);e.setAttribute('aria-hidden','true');return e;};
const upstream='https://github.com/zephyrproject-rtos/zephyr';
const fold=v=>String(v??'').toLowerCase();
const cmp=(a,b)=>a.localeCompare(b,undefined,{numeric:true,sensitivity:'base'});
const groupedCategories=new Set(['driver','sensor','docs','other','dts','soc','board_change','board','board_candidate','board_feature']);
const scopedCategories=new Set(['soc','board_change','board','board_candidate','board_feature']);
const driverCategories=new Set(['driver','sensor']);
const genericDriver=new Set('main common core init utils util test tests driver drivers config cmakelists kconfig makefile readme sample shell api types module binding bindings build index'.split(' '));
const unique=values=>[...new Set(values.filter(Boolean))];
function driverIdentity(rows){
  const subs=[],names=[];
  for(const e of rows){const parts=(e.path||'').split('/');if(parts.length<3||parts[0]!=='drivers')continue;
    const sub=parts[1],file=parts.at(-1);subs.push(sub);let stem=file.replace(/\.[^.]*$/,'').toLowerCase();
    if(file.startsWith('Kconfig.'))stem=file.slice(8).toLowerCase();
    else if(/^(kconfig|cmakelists|readme)/i.test(file))stem='';
    else if(parts.length>3){if(sub==='sensor'&&parts.length>4)stem=parts[3].toLowerCase();else if(sub!=='sensor')stem=parts[2].toLowerCase();}
    if(stem.startsWith(sub+'_'))stem=stem.slice(sub.length+1);if(stem.endsWith('_'+sub))stem=stem.slice(0,-sub.length-1);if(stem===sub)stem='';
    if(stem&&!genericDriver.has(stem)&&/^[a-z0-9][a-z0-9_.-]*$/.test(stem))names.push(stem);
  }
  const prefix=(rows[0].commit_subject||'').match(/^drivers?\s*:\s*([\w-]+)\s*:/i);if(!subs.length&&prefix)subs.push(prefix[1].toLowerCase());if(!subs.length&&rows[0].kind==='sensor')subs.push('sensor');
  return [unique(subs).join(', ')||'Not identified',unique(names).join(', ')||'Subsystem-level / not identified'];
}
function groupScope(e,category){const path=e.path||'',parts=path.split('/'),subject=e.subject;
  if(['board_change','board','board_candidate','board_feature'].includes(category)){const folder=parts.length>=4&&parts[0]==='boards'?parts.slice(0,3).join('/'):'';return [[folder,subject,...(category==='board_feature'?[e.change_type??null,e.detail??null,e.confidence??null]:[])],subject];}
  if(category==='soc'){if(parts.length>=3&&parts[0]==='soc'){const folder=parts.slice(0,parts.length>=4?3:2).join('/');if(subject===parts.at(-1)||subject===parts.slice(0,-1).join('/'))return [[folder,''],folder];return [[folder,subject],subject];}return [[path,subject],subject];}return [[], ''];
}
function groupEvents(events,category){
  const groups=new Map();for(const e of events){const key=JSON.stringify([e.sha,groupScope(e,category)[0]]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e);}
  return [...groups.values()].map(rows=>{const subjects=unique(rows.map(e=>e.subject)),files=new Map();for(const e of rows){if(!e.path)continue;const key=JSON.stringify([e.path,e.source_revision||e.sha]);if(!files.has(key))files.set(key,[]);files.get(key).push(e);}const [subsystem,driver]=driverCategories.has(category)?driverIdentity(rows):['',''];return {rows,subjects,subject:groupScope(rows[0],category)[1]||subjects.join(', '),files,subsystem,driver,types:unique(rows.map(e=>e.change_type||'Unknown'))};});
}
// Logical column IDs are stable even when a category omits redundant columns.
function newsColumns(category,grouped){
  const cols=new Map([[0,'UTC date / time'],[1,'Category'],[2,'Subject / target'],[3,'Headline'],[4,'Confidence'],[5,'Release'],[6,'Commit']]);
  if(!grouped){if(category){cols.delete(1);cols.set(2,'Board / target');cols.set(3,'Commit description');}return cols;}
  cols.set(3,'Commit description');cols.set(4,'Files');
  if(driverCategories.has(category)){cols.set(1,'Subsystem');cols.set(2,'Driver');if(category==='sensor')cols.delete(1);}
  else{if(!['all','release_news'].includes(category))cols.delete(1);if(category==='soc')cols.set(2,'SoC / family');else if(scopedCategories.has(category))cols.set(2,'Board / target');else cols.delete(2);}
  return cols;
}
function tableHead(hr,dataCols,columns){dataCols.span=columns.size;const th=node('th',undefined,'pulse-news-expand');th.scope='col';th.append(node('span','Details','pulse-sr-only'));hr.append(th);for(const [id,label] of columns){const th=node('th',label);th.scope='col';th.dataset.newsColumn=String(id);hr.append(th);}}
function renderGrouped(target,events,boards,category,commitFiles={}){
  target.replaceChildren();if(!events.length){target.append(node('p','No matching commits in this window.'));return;}
  const driver=driverCategories.has(category),mixed=['all','release_news'].includes(category),columns=newsColumns(category,true),groups=groupEvents(events,category),root=node('div',undefined,'pulse-news-table pulse-grouped-news pulse-compact-news');Object.assign(root.dataset,{pulseNews:'100',groupUnit:category==='board_feature'?'capability signals':scopedCategories.has(category)?'commit groups':'commits',groupCategory:category,fixedCategory:mixed?'':category});
  const summary=node('p',undefined,'pulse-group-summary'),scroll=node('div',undefined,'pulse-news-scroll'),table=node('table',undefined,'pulse-news-list'),head=node('thead'),hr=node('tr'),body=node('tbody'),cols=node('colgroup');cols.append(node('col',undefined,'pulse-news-expand-col'));const dataCols=node('col');dataCols.span=7;cols.append(dataCols);
  tableHead(hr,dataCols,columns);head.append(hr);table.append(cols,head,body);scroll.append(table);root.append(summary,scroll);target.append(root);
  const link=(text,url,ico)=>{const a=node('a',undefined,'pulse-detail-link');a.href=url;a.append(glyph(ico),' ',node('span',text));return a;};
  function evidence(e){return node('li',`${mixed?labels[e.kind]+' · ':''}${e.subject} · ${e.change_type||'Unknown'} · ${e.confidence||'unknown'}: ${e.detail||''}`);}
  for(const g of groups){const e=g.rows[0],sha=e.sha,headline=e.commit_subject||e.subject,stamp=String(e.committed||'').slice(0,16).replace('T',' '),release=e.release?.first_release||(e.release?.status==='main_only'?'Not in tracked releases':'Unknown'),linked=unique(g.rows.flatMap(e=>e.boards||[])).map(id=>boards.get(id)).filter(Boolean),vendors=linked.map(b=>b.vendor_name||b.vendor||'').join(' '),manifest=Object.hasOwn(commitFiles,sha)?commitFiles[sha]:null, files=manifest===null?[...g.files].map(([key,items])=>{const [path,revision]=JSON.parse(key);return {path,revision,items};}):manifest.map(f=>({...f,items:g.files.get(JSON.stringify([f.path,f.revision]))||[]})), fileCount=new Set(files.map(f=>f.path)).size, keys=new Set(files.map(f=>JSON.stringify([f.path,f.revision]))),extra=manifest===null?[]:[...g.files].filter(([key])=>!keys.has(key)).map(([key,items])=>{const [path,revision]=JSON.parse(key);return {path,revision,items,extra:true};});
    const kinds=unique(g.rows.map(e=>e.kind)),categoryText=mixed?kinds.map(k=>labels[k]).join(', '):labels[category];const row=node('tr',undefined,'pulse-news-row pulse-cat-'+(mixed?e.kind:category));Object.assign(row.dataset,{kind:mixed?e.kind:category,kinds:JSON.stringify(kinds),time:e.committed||'',changeType:g.types.join(', '),changeTypes:JSON.stringify(g.types),subjects:JSON.stringify(unique([...g.subjects,g.subject])),scope:scopedCategories.has(category)?g.subject:'',subsystem:g.subsystem,driver:g.driver,vendor:vendors,eventCount:String(g.rows.length)});
    const td=node('td',undefined,'pulse-news-expand'),btn=node('button',undefined,'pulse-news-toggle');btn.type='button';btn.setAttribute('aria-label','Details for '+headline);const arrow=node('span','▸');arrow.setAttribute('aria-hidden','true');btn.append(arrow);td.append(btn);row.append(td);
    [stamp,driver?g.subsystem:categoryText,driver?g.driver:g.subject,headline,manifest===null?String(fileCount)+'+':String(fileCount),release,sha.slice(0,10)].forEach((value,i)=>{if(!columns.has(i))return;const cell=node('td',value,'pulse-news-col-'+i);cell.title=value;if(i===3||i===6){const b=node('button',value,'pulse-commit-expand');b.type='button';cell.replaceChildren(b);}else if(i===1&&mixed){cell.replaceChildren();kinds.forEach((k,j)=>{if(j)cell.append(' · ');cell.append(glyph(icons[k]),' '+labels[k]);});}else if(i===2&&['board','board_candidate','board_change','board_feature'].includes(category)&&g.subjects.length===1&&g.subjects[0]===value){const profile=linked.find(b=>b.url===e.board_profile_url&&/^boards\/[\w.-]+\.html$/.test(b.url||''));if(profile){const a=node('a',value,'pulse-board-profile-link');a.href=profile.url;cell.replaceChildren(a);}}if(i===2&&category==='board_feature'){cell.append(node('span',`${e.detail||''} · ${e.confidence||'unknown'}`,'pulse-signal-preview'));cell.dataset.sortValue=value;}if(i===4)cell.dataset.sortValue=String(fileCount);if(i===5&&value==='Not in tracked releases')cell.textContent='Not in tags';row.append(cell);});
    const detail=node('tr',undefined,'pulse-news-detail'),cell=node('td');cell.colSpan=columns.size+1;detail.append(cell);
    const statuses={A:'Added',M:'Modified',D:'Deleted',R:'Renamed',C:'Copied',T:'Type changed'};
    // Search the complete group before constructing its detail DOM. This keeps large
    // commits and multiple board-scoped groups cheap until the user expands them.
    row.pulseSearchText=[sha,categoryText,g.subject,g.subsystem,g.driver,vendors,release,e.release?.latest_release,...(e.release?.lts_tags||[]),...linked.map(b=>b.name),...g.rows.flatMap(e=>[e.subject,e.change_type,e.confidence,e.detail]),...[...files,...extra].flatMap(f=>[f.path,f.old_path,statuses[f.status],f.revision])].filter(Boolean).join(' ');
    detail.pulsePopulate=()=>{const panel=node('article',undefined,'pulse-news-detail-panel');panel.append(node('strong',headline),node('p',`${stamp} UTC · ${categoryText} · ${release} (exact commit inclusion)`));if(e.release?.latest_release||e.release?.lts_tags?.length)panel.append(node('p',`Latest tracked containing tag: ${e.release.latest_release||'Unknown'} · LTS tags: ${(e.release.lts_tags||[]).join(', ')||'None'}`));if(scopedCategories.has(category))panel.append(node('p','Hardware scope: '+g.subject));if(driver)panel.append(node('p',`Subsystem: ${g.subsystem} · Driver: ${g.driver}`));if(vendors)panel.append(node('p','Vendor association: '+vendors));const count=node('p');count.append(node('strong',manifest===null?`Known evidence files (${fileCount}) — complete diff unavailable`:`Affected files (${fileCount}) — complete commit`),` · ${g.rows.length} classified events in this category/group`);panel.append(count);
    const list=node('ul',undefined,'pulse-affected-files');for(const f of [...files,...extra]){const {path,revision,items}=f,li=node('li'),notes=node('ul');li.append(link(path,upstream+'/blob/'+encodeURIComponent(revision)+'/'+path.split('/').map(encodeURIComponent).join('/'),'github'));const note=statuses[f.status]||(f.extra?'Additional evidence':'');if(note)li.append(' · '+note+(f.old_path?' from '+f.old_path:''));if(revision!==sha)li.append(' (before removal)');if(items.length){notes.append(...items.map(evidence));li.append(notes);}list.append(li);}list.append(...g.rows.filter(e=>!e.path).map(evidence));panel.append(list);
    const links=node('p',undefined,'pulse-news-links');links.append(link('View upstream commit',upstream+'/commit/'+encodeURIComponent(sha),'commit'));for(const b of linked)if(/^boards\/[\w.-]+\.html$/.test(b.url||''))links.append(link(b.name,b.url,'board'));links.append(link('Related hardware / news','hardware-search.html?subject='+encodeURIComponent(sha),'search'));panel.append(links);cell.append(panel);detail.pulsePopulate=null;};body.append(row,detail);
  }
  init(root);
}

let serial=0;
function init(root){
  if(root.dataset.pulseReady)return;
  const body=root.querySelector('tbody');if(!body)return;
  const pairs=[...body.querySelectorAll('tr.pulse-news-row')].map((row,i)=>({row,detail:row.nextElementSibling,i})).filter(p=>p.detail?.classList.contains('pulse-news-detail'));
  if(!pairs.length)return;
  root.dataset.pulseReady='true';
  const logicalColumns=[...root.querySelectorAll('thead th')].map((th,i)=>i===0?null:Number(th.dataset.newsColumn??i-1));const physical=id=>logicalColumns.indexOf(id);const fixed=!!root.dataset.fixedCategory;
  const grouped=!!root.dataset.groupUnit, driver=driverCategories.has(root.dataset.groupCategory), totalEvents=pairs.reduce((n,p)=>n+Number(p.row.dataset.eventCount||1),0);
  const unit=root.dataset.groupUnit||'events'; const values=(p,key,fallback=[])=>p.row.dataset[key]?JSON.parse(p.row.dataset[key]):fallback;
  const uid='pulse-news-'+(++serial); const controls=node('div',undefined,'pulse-news-controls');
  function field(title,el){const l=node('label',title);el.setAttribute('aria-label',title);l.append(el);controls.append(l);return el;}
  const query=field('Filter news',node('input'));query.type='search';query.placeholder=grouped?'Subsystem, driver, description, file, SHA…':'Board, vendor, headline, SHA…';
  const category=field('Category',node('select'));category.append(new Option('All categories',''));for(const k of Object.keys(labels))if(pairs.some(p=>values(p,'kinds',[p.row.dataset.kind]).includes(k)))category.append(new Option(labels[k],k));
  if(fixed)category.parentElement.hidden=true;
  let subsystem=null,driverFilter=null; if(driver){const choices=(key,title)=>{const el=field(title,node('select'));el.append(new Option('All '+title.toLowerCase()+'s',''));for(const v of unique(pairs.flatMap(p=>(p.row.dataset[key]||'').split(', '))).sort(cmp))el.append(new Option(v,v));return el;};if(physical(1)>=0)subsystem=choices('subsystem','Subsystem');driverFilter=choices('driver','Driver');}
  let scopeFilter=null;if(scopedCategories.has(root.dataset.groupCategory)){const label=root.dataset.groupCategory==='soc'?'SoC / family':'Board / target';scopeFilter=field(label,node('select'));scopeFilter.append(new Option('All '+(root.dataset.groupCategory==='soc'?'SoCs / families':'boards / targets'),''));for(const v of unique(pairs.map(p=>p.row.dataset.scope)).sort(cmp))scopeFilter.append(new Option(v,v));}
  const changeType=field('Change type',node('select'));changeType.append(new Option('All change types',''));for(const t of [...new Set(pairs.flatMap(p=>values(p,'changeTypes',[p.row.dataset.changeType||'Unknown'])))].sort(cmp))changeType.append(new Option(t,t));
  const sort=field('Sort by',node('select'));const options=[['newest','Newest first'],['oldest','Oldest first'],['change_type','Change type'],['vendor','Vendor association']];
  for(const [id,key] of [[1,'category'],[2,'subject'],[3,'headline'],[4,'confidence'],[5,'release'],[6,'commit']])if(physical(id)>=0)options.push([key,root.querySelectorAll('thead th')[physical(id)].textContent.trim()]);
  for(const [v,t] of options)sort.append(new Option(t,v));
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
  function expand(p,on){if(on&&p.detail.pulsePopulate)p.detail.pulsePopulate();p.open=on;p.detail.hidden=!on||p.row.hidden;p.button.setAttribute('aria-expanded',String(on));p.button.firstElementChild.textContent=on?'▾':'▸';for(const b of p.row.querySelectorAll('.pulse-commit-expand'))b.setAttribute('aria-expanded',String(on));}
  for(const p of pairs){p.button=p.row.querySelector('button');p.detail.id=uid+'-'+p.i;p.button.setAttribute('aria-controls',p.detail.id);p.text=fold(p.row.textContent+' '+(p.row.pulseSearchText||p.detail.textContent)+' '+p.row.dataset.vendor);p.subject=p.row.querySelector('.pulse-news-col-2')?.textContent.trim()||'';p.subjects=values(p,'subjects',[p.subject]);for(const b of p.row.querySelectorAll('.pulse-commit-expand')){b.setAttribute('aria-controls',p.detail.id);b.addEventListener('click',()=>{expand(p,!p.open);updateToggle();});}
    const subjectLinks=[...p.row.querySelectorAll('.pulse-subject-filter'),...p.detail.querySelectorAll('.pulse-subject-filter')];if(!preview)for(const subjectLink of subjectLinks)subjectLink.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();setSubject(fold(subjectFilter)===fold(p.subject)?'':p.subject);});expand(p,false);p.button.addEventListener('click',()=>{expand(p,!p.open);updateToggle();});p.row.addEventListener('click',e=>{if(e.target.closest('button,a,input,select')||String(window.getSelection()).length)return;expand(p,!p.open);updateToggle();});}
  function updateToggle(){toggleAll.textContent=shown.length&&shown.every(p=>p.open)?'Collapse page':'Expand page';toggleAll.disabled=!shown.length;}
  function draw(){
    const terms=fold(query.value).trim().split(/\s+/).filter(Boolean);const k=category.value;
    const result=pairs.filter(p=>(!k||values(p,'kinds',[p.row.dataset.kind]).includes(k))&&(!changeType.value||values(p,'changeTypes',[p.row.dataset.changeType||'Unknown']).includes(changeType.value))&&(!subjectFilter||p.subjects.some(s=>fold(s)===fold(subjectFilter)))&&(!scopeFilter?.value||p.row.dataset.scope===scopeFilter.value)&&(!subsystem?.value||p.row.dataset.subsystem.split(', ').includes(subsystem.value))&&(!driverFilter?.value||p.row.dataset.driver.split(', ').includes(driverFilter.value))&&terms.every(t=>p.text.includes(t)));
    active.hidden=!subjectFilter;active.textContent='Subject: '+subjectFilter+' ×';active.setAttribute('aria-label','Clear subject filter');
    for(const p of pairs){for(const a of [...p.row.querySelectorAll('.pulse-subject-filter'),...p.detail.querySelectorAll('.pulse-subject-filter')]){a.classList.toggle('pulse-filter-active',!!subjectFilter&&fold(p.subject)===fold(subjectFilter));a.title=subjectFilter&&fold(p.subject)===fold(subjectFilter)?'Remove subject filter':'Filter by this subject';}}
    const cell=(p,n)=>{const c=p.row.querySelector('.pulse-news-col-'+n);return c?.dataset.sortValue??c?.textContent.trim()??'';};
    result.sort((a,b)=>{if(headerSort){const n=logicalColumns[headerSort.index];return headerSort.dir*cmp(n===0?a.row.dataset.time:cell(a,n),n===0?b.row.dataset.time:cell(b,n))||a.i-b.i;}let r=0;switch(sort.value){case 'change_type':r=cmp(a.row.dataset.changeType||'Unknown',b.row.dataset.changeType||'Unknown');break;case 'oldest':r=cmp(a.row.dataset.time,b.row.dataset.time);break;case 'category':r=cmp(cell(a,1),cell(b,1));break;case 'subject':r=cmp(cell(a,2),cell(b,2));break;case 'vendor':r=cmp(a.row.dataset.vendor||'\uffff',b.row.dataset.vendor||'\uffff');break;case 'confidence':r=grouped?cmp(cell(a,4),cell(b,4)):cmp(a.row.dataset.confidence,b.row.dataset.confidence);break;case 'headline':r=cmp(cell(a,3),cell(b,3));break;case 'release':r=cmp(cell(a,5),cell(b,5));break;case 'commit':r=cmp(cell(a,6),cell(b,6));break;default:r=cmp(b.row.dataset.time,a.row.dataset.time);}return r||a.i-b.i;});
    const count=size.value==='all'?Math.max(1,result.length):Number(size.value)||100;const pages=Math.max(1,Math.ceil(result.length/count));page=Math.max(0,Math.min(page,pages-1));shown=result.slice(page*count,(page+1)*count);const visible=new Set(shown),matched=new Set(result);
    const frag=document.createDocumentFragment();for(const p of [...result,...pairs.filter(p=>!matched.has(p))]){p.row.hidden=!visible.has(p);p.detail.hidden=p.row.hidden||!p.open;frag.append(p.row,p.detail);}body.append(frag);
    status.textContent=result.length?`${page*count+1}–${Math.min(result.length,(page+1)*count)} of ${result.length} ${unit} · ${pairs.length} total`:`No matches · ${pairs.length} total`;if(grouped)root.querySelector('.pulse-group-summary').textContent=`${result.length} matching ${unit} · ${result.reduce((n,p)=>n+Number(p.row.dataset.eventCount),0)} of ${totalEvents} ${root.dataset.evidenceLabel||'classified events'}. File counts cover the complete commit when available; + means partial evidence.`;
    prev.disabled=page===0;next.disabled=page+1>=pages;updateToggle();
  }
  for(const e of [query,category,changeType,sort,size,subsystem,driverFilter,scopeFilter].filter(Boolean))e.addEventListener(e===query?'input':'change',()=>{if(e===sort&&sort.value!=='column'){headerSort=null;sort.querySelector('option[value=column]')?.remove();const mapping={newest:[1,-1],oldest:[1,1],category:[2,1],subject:[3,1],confidence:[5,1],headline:[4,1],release:[6,1],commit:[7,1]};const m=mapping[sort.value];sorter?.show(m?physical(m[0]-1):null,m?.[1]);}page=0;draw();});
  prev.onclick=()=>{page--;draw();root.scrollIntoView({block:'start'});};next.onclick=()=>{page++;draw();root.scrollIntoView({block:'start'});};toggleAll.onclick=()=>{const on=!shown.every(p=>p.open);shown.forEach(p=>expand(p,on));updateToggle();};draw();
}
function render(target,events,boards,limit=100,relatedEvents=events,category=null){
  target.replaceChildren();if(!category||!events.length)target.append(node('p',`${events.length} matching events${events.length>limit?` (showing ${limit})`:''}.`));if(!events.length)return;
  const columns=newsColumns(category,false),root=node('div',undefined,'pulse-news-table'+(category?' pulse-compact-news':''));root.dataset.pulseNews='100';if(category)root.dataset.fixedCategory=category;const scroll=node('div',undefined,'pulse-news-scroll'),table=node('table',undefined,'pulse-news-list'),head=node('thead'),hr=node('tr'),body=node('tbody');
  const cols=node('colgroup');cols.append(node('col',undefined,'pulse-news-expand-col'));const dataCols=node('col');dataCols.span=7;cols.append(dataCols);
  tableHead(hr,dataCols,columns);head.append(hr);table.append(cols,head,body);scroll.append(table);root.append(scroll);target.append(root);
  const relatedBySubject=new Map();for(const e of relatedEvents){const key=fold(e.subject);if(!relatedBySubject.has(key))relatedBySubject.set(key,new Set());if(Object.hasOwn(labels,e.kind))relatedBySubject.get(key).add(e.kind);}
  for(const e of events.slice(0,limit)){
    const kind=Object.hasOwn(labels,e.kind)?e.kind:'other',subject=String(e.subject||''),headline=e.commit_subject||subject,confidence=String(e.confidence||'unknown'),stamp=String(e.committed||'').slice(0,16).replace('T',' '),release=e.release?.first_release||(e.release?.status==='main_only'?'Not in tracked releases':'Unknown');
    const linked=(e.boards||[]).map(id=>boards.get(id)).filter(Boolean),profile=linked.find(b=>b.url===e.board_profile_url&&/^boards\/[\w.-]+\.html$/.test(b.url||'')),vendors=linked.map(b=>b.vendor_name||b.vendor||'').join(' ');
    const row=node('tr',undefined,'pulse-news-row pulse-cat-'+kind);Object.assign(row.dataset,{kind,changeType:e.change_type||'Unknown',time:e.committed||'',vendor:vendors,confidence});const td=node('td',undefined,'pulse-news-expand'),btn=node('button',undefined,'pulse-news-toggle');btn.type='button';btn.setAttribute('aria-label','Details for '+subject);const arrow=node('span','▸');arrow.setAttribute('aria-hidden','true');btn.append(arrow);td.append(btn);row.append(td);
    [stamp,labels[kind],subject,headline,confidence,release,String(e.sha||'').slice(0,10)].forEach((value,i)=>{if(!columns.has(i))return;const cell=node('td',value,'pulse-news-col-'+i);cell.title=value;if(category&&i===5&&value==='Not in tracked releases')cell.textContent='Not in tags';if(category&&(i===3||i===6)){const b=node('button',value,'pulse-commit-expand');b.type='button';cell.replaceChildren(b);}else if(i===1||i===2){const a=node('a',value,i===1?'pulse-category-link':'pulse-subject-filter');a.href=kind+'.html'+(i===2?'?subject='+encodeURIComponent(subject):'');if(i===1)a.prepend(glyph(icons[kind]),' ');else if(profile){a.className='pulse-board-profile-link';a.href=profile.url;a.title='Open board profile';}else a.dataset.subject=subject;cell.replaceChildren(a);}row.append(cell);});
    const detail=node('tr',undefined,'pulse-news-detail'),cell=node('td'),panel=node('article',undefined,'pulse-news-detail-panel');cell.colSpan=columns.size+1;panel.append(node('strong',subject),node('p',headline),node('p',e.detail||''),node('p','Change type: '+(e.change_type||'Unknown')),node('p',`${stamp} UTC · ${labels[kind]} · ${confidence} · ${release} (exact commit inclusion)`));if(profile){const f=node('p','Subject filter: '),a=node('a',subject,'pulse-subject-filter');f.prepend(glyph('filter'),' ');a.dataset.subject=subject;a.href=kind+'.html?subject='+encodeURIComponent(subject);f.append(a);panel.append(f);}if(vendors)panel.append(node('p','Vendor association: '+vendors));if(e.path)panel.append(node('p','Source: '+e.path+(e.source_revision&&e.source_revision!==e.sha?' (before removal)':'')));
    const links=node('p',undefined,'pulse-news-links');
    const link=(text,url,ico,title)=>{const a=node('a',undefined,'pulse-detail-link');a.href=url;if(title)a.title=title;a.append(glyph(ico),' ',node('span',text));return a;};
    const sha=encodeURIComponent(e.sha||'');links.append(link('Commit '+e.sha,upstream+'/commit/'+sha,'commit','View commit on GitHub'));
    if(e.path)links.append(link('Source file',upstream+'/blob/'+encodeURIComponent(e.source_revision||e.sha||'')+'/'+e.path.split('/').map(encodeURIComponent).join('/'),'github','View source file on GitHub'));
    for(const b of linked)if(/^boards\/[\w.-]+\.html$/.test(b.url||''))links.append(link(b.name,b.url,'board','Open board profile: '+b.name));
    const related=[...(relatedBySubject.get(fold(subject))||[])].filter(k=>k!==kind);for(const k of related)links.append(link(labels[k],k+'.html?subject='+encodeURIComponent(subject),icons[k]));
    links.append(link('Related hardware / news','hardware-search.html?subject='+encodeURIComponent(subject),'search'));panel.append(links);cell.append(panel);detail.append(cell);body.append(row,detail);
  }
  init(root);
}
window.PulseNews={init,render,renderGrouped,groupEvents};async function start(){document.querySelectorAll('[data-pulse-news]').forEach(init);const mounts=[...document.querySelectorAll('[data-pulse-category]')];if(!mounts.length)return;try{const {data}=await window.PulsePreferences.load('data/news-view.json');const boards=new Map(data.boards.map(b=>[b.id,b]));for(const m of mounts){const category=m.dataset.pulseCategory,items=category==='all'?data.events:category==='release_news'?data.events.filter(e=>!['docs','other'].includes(e.kind)):data.events.filter(e=>e.kind===category);if(groupedCategories.has(category)||['all','release_news'].includes(category))renderGrouped(m,items,boards,category,data.commit_files||{});else render(m,items,boards,items.length,data.events,category);}}catch(e){for(const m of mounts)m.textContent='News unavailable. Use the raw JSON or All commits link below, or refresh.';}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
