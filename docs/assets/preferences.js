/* One browser preference store for all pages. No network writes. */
((global) => {
  'use strict';
  const KEY='zephyr-pulse-preferences-v3', OLD='zephyr-pulse-watchlist-v2';
  const defaults={boards:[],vendors:[],peripherals:[],requirements:['ethernet','can-fd','usb','crypto'],selected:[],baseline:'main',comparison_rows:'all',search:'',matches_only:false,explorer_search:'',explorer_watched:false,vendor:'',home_limit:8,watch_limit:100,theme:'default',hardware_query:'',hardware_kind:'all',hardware_vendor:'',hardware_capability:'',hardware_from:'',hardware_to:'',hardware_watched:false};
  const lists=['boards','vendors','peripherals','requirements','selected'];
  const text=['baseline','search','explorer_search','vendor','hardware_query','hardware_vendor','hardware_capability'];
  const flags=['matches_only','explorer_watched','hardware_watched'];
  const choices={comparison_rows:['all','required','differences'],theme:['default','light','dark'],hardware_kind:['all','target','board_feature','board_candidate','board','board_change','sensor','driver','soc','dts','dt_bindings','subsys','samples','tests','manifest','docs','other','pr','vendor','release']};
  function clean(value){
    const out={}; if(!value||typeof value!=='object'||Array.isArray(value))return out;
    for(const k of lists) if(Array.isArray(value[k])&&value[k].every(x=>typeof x==='string')) out[k]=[...new Set(value[k].map(x=>x.trim()).filter(x=>x&&x.length<=512))].slice(0,k==='selected'?8:200);
    for(const k of text) if(typeof value[k]==='string'&&value[k].length<=512)out[k]=value[k];
    for(const k of flags)if(typeof value[k]==='boolean')out[k]=value[k];
    for(const [k,v] of Object.entries(choices))if(v.includes(value[k]))out[k]=value[k];
    for(const [k,max] of [['home_limit',50],['watch_limit',500]])if(Number.isInteger(value[k])&&value[k]>=1&&value[k]<=max)out[k]=value[k];
    for(const k of ['hardware_from','hardware_to'])if(typeof value[k]==='string'&&(value[k]===''||/^\d{4}-\d{2}-\d{2}$/.test(value[k])))out[k]=value[k];
    if(out.requirements)out.requirements=[...new Set(out.requirements.map(x=>x.toLowerCase()))];
    return out;
  }
  function create(data={},storage){
    const base={...defaults,...clean(data.preferences),...clean(data.watchlist)};
    let custom={}, available=true;
    try {const current=storage.getItem(KEY);if(current!==null)custom=clean(JSON.parse(current));else {const old=storage.getItem(OLD);if(old!==null){custom=clean(JSON.parse(old));storage.setItem(KEY,JSON.stringify(custom));}}}catch(_){available=false;}
    const persist=()=>{try{storage.setItem(KEY,JSON.stringify(custom));available=true;}catch(_){available=false;}return available;};
    return {get:()=>({...base,...custom}),defaults:()=>({...base}),saved:()=>available,update:patch=>{custom={...custom,...clean(patch)};return persist();},replace:patch=>{custom=clean(patch);return persist();},reset:()=>{custom={};return persist();},export:()=>({version:3,preferences:{...base,...custom}})};
  }
  function joinCatalog(catalog,dynamic,news){const data={...catalog,...dynamic,events:news.events||[],commit_files:news.commit_files||{}};data.comparison={...data.comparison,targets:data.comparison.targets.map(t=>({...t,...(dynamic.target_activity?.[t.id]||{})}))};data.boards=(data.boards||[]).map(b=>Object.hasOwn(dynamic.board_activity||{},b.id)?{...b,last_activity:dynamic.board_activity[b.id]}:b);return data;}
  const api={create,clean,defaults,KEY,joinCatalog};
  if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
  const base=new URL('../',document.currentScript.src);
  const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  const link=(text,path)=>{const a=node('a',text);a.href=new URL(path,base);return a;};
  const split=v=>v.split(',').map(x=>x.trim()).filter(Boolean);
  const promises=new Map();
  function load(view='intelligence.json'){
    if(!promises.has(view)){
      const task=(async()=>{const r=await fetch(new URL(view,base));if(!r.ok){if(view!=='intelligence.json'&&r.status===404)return load();throw Error('HTTP '+r.status);}let data=await r.json();if(view==='intelligence.json'&&data.schema_version===3){const [a,n]=await Promise.all([fetch(new URL('data/activity.json',base)),fetch(new URL('data/news-view.json',base))]);if(!a.ok||!n.ok)throw Error('Activity/news HTTP '+a.status+'/'+n.status);const [dynamic,news]=await Promise.all([a.json(),n.json()]);data=joinCatalog(data,dynamic,news);}let storage;try{storage=global.localStorage;}catch(_){}return {data,store:create(data,storage)};})();
      promises.set(view,task);task.catch(()=>promises.delete(view));
    }
    return promises.get(view);
  }
  const button=(text,action)=>{const b=node('button',text);b.type='button';b.addEventListener('click',action);return b;};
  function theme(value){global.PulseTheme?.apply(value);}
  function settings(el,data,store){
    let prefs=store.get(); const controls={};const form=node('form');form.className='pulse-settings-form';
    const notice=node('p');notice.className='pulse-settings-status';notice.setAttribute('role','status');
    const sections={};
    for(const [id,title,icon,desc] of [
      ['watch','Watchlists','watch','Follow boards, vendors and peripherals without hiding global news.'],
      ['compare','Hardware comparison','compare','Set requirements and choose the upstream baseline for your next design.'],
      ['display','Display and discovery','settings','Personalize the appearance and board explorer.'],
      ['search','Hardware search defaults','search','Choose the filters used when you open hardware search.']]){
      const field=node('fieldset');field.className='pulse-settings-card';const legend=node('legend');const symbol=node('span');symbol.className='pulse-icon pulse-i-'+icon;symbol.setAttribute('aria-hidden','true');legend.append(symbol,node('span',title));field.append(legend);const intro=node('p',desc);intro.className='pulse-settings-help';field.append(intro);form.append(field);sections[id]=field;
    }
    const field=(group,k,title,type,opts)=>{const label=node('label');label.className='pulse-setting-field'+(type==='checkbox'?' pulse-setting-check':'');const caption=node('span',title);caption.className='pulse-setting-label';let input;
      if(type==='select'){input=node('select');for(const [v,t] of opts){const o=node('option',t);o.value=v;input.append(o);}}
      else {input=node('input');input.type=type==='list'?'text':type;if(type==='number'){input.min=1;input.max=k==='home_limit'?50:500;}}
      controls[k]={input,type};if(type==='checkbox')label.append(input,caption);else label.append(caption,input);sections[group].append(label);return input;};
    field('watch','boards','Board / SoC patterns (comma separated)','list').placeholder='*mcxn*, ra8P1';field('watch','vendors','Vendor patterns','list').placeholder='nxp, renesas';field('watch','peripherals','Peripheral patterns','list').placeholder='ethernet, can-fd';
    sections.watch.append(node('p','Case-insensitive globs (*, ?, [abc]) or plain substring matches. Empty lists override YAML. Global news remains unfiltered.'));
    field('compare','requirements','Required capabilities (comma separated)','list');
    const baselines=[['main','Main branch'],...(data.comparison?.snapshots||[]).map(s=>[s.tag,`${s.tag} — ${s.latest_stable?'latest stable; ':''}${s.lts?'configured LTS; ':''}${s.lifecycle}`])];
    if(!baselines.some(([v])=>v===prefs.baseline))baselines.push([prefs.baseline,`${prefs.baseline} (not in current snapshot)`]);
    field('compare','baseline','Comparison baseline','select',baselines);field('compare','comparison_rows','Capability rows','select',[['all','All known capabilities'],['required','Required capabilities only'],['differences','Differences + required']]);field('compare','search','Default comparator search','text');field('compare','matches_only','Discover only targets declaring all requirements','checkbox');
    const selected=node('p');const targetActions=node('div');targetActions.className='pulse-settings-row';targetActions.append(link('Manage selected targets in comparator','compare.html'),button('Clear selected targets',()=>{prefs.selected=[];selected.textContent='0 selected targets (save to apply).';notice.textContent='Unsaved changes — select Save preferences.';}));sections.compare.append(selected,targetActions);
    field('display','explorer_search','Board explorer search','text');field('display','explorer_watched','Watchlist-only board explorer (not global news)','checkbox');
    field('display','vendor','Default vendor chart (namespace)','text');field('display','home_limit','Homepage watchlist entries (1–50)','number');field('display','watch_limit','Watchlist page entries (1–500)','number');field('display','theme','Theme','select',[['default','Use theme control / default'],['light','Light'],['dark','Dark']]);
    field('search','hardware_query','Hardware search terms','text');field('search','hardware_vendor','Hardware search vendor','text');field('search','hardware_capability','Hardware search capabilities','text');field('search','hardware_kind','Hardware search result type','select',choices.hardware_kind.map(v=>[v,v.replaceAll('_',' ')]));field('search','hardware_from','Search date from (UTC)','date');field('search','hardware_to','Search date through (UTC)','date');field('search','hardware_watched','Search only my watchlist','checkbox');sections.search.append(link('Open hardware search','hardware-search.html'));
    const loadFields=()=>{prefs=store.get();for(const [k,{input,type}] of Object.entries(controls)){if(type==='checkbox')input.checked=prefs[k];else input.value=type==='list'?prefs[k].join(', '):prefs[k];}selected.textContent=`${prefs.selected.length} selected targets.`;};
    const save=node('button','Save preferences');save.type='submit';const savebar=node('div');savebar.className='pulse-settings-savebar';savebar.append(save,notice);form.append(savebar);form.addEventListener('input',()=>{notice.textContent='Unsaved changes — select Save preferences.';});form.addEventListener('submit',e=>{e.preventDefault();const patch={selected:prefs.selected};for(const [k,{input,type}] of Object.entries(controls))patch[k]=type==='checkbox'?input.checked:type==='list'?split(input.value):type==='number'?Number(input.value):input.value;const ok=store.update(patch);theme(store.get().theme);notice.textContent=ok?'Saved in this browser.':'Storage unavailable; changes apply only until this page is closed.';loadFields();});
    const transfer=node('section');transfer.className='pulse-settings-transfer';transfer.append(node('h2','Import / export / reset'),node('p','Export saved preferences to move them to another browser or project. Import and reset replace saved preferences.'));const actions=node('div');actions.className='pulse-actions';
    actions.append(button('Export JSON',()=>{const blob=new Blob([JSON.stringify(store.export(),null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download='zephyr-pulse-preferences.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}));
    const file=node('input');file.type='file';file.accept='.json,application/json';file.hidden=true;actions.append(button('Import JSON',()=>file.click()),file);
    file.addEventListener('change',async()=>{try{const f=file.files[0];if(!f)return;if(f.size>1000000)throw Error();const x=JSON.parse(await f.text());if(x.version!==3||!x.preferences||typeof x.preferences!=='object'||Array.isArray(x.preferences)||!Object.keys(clean(x.preferences)).length)throw Error();if(!global.confirm('Replace current saved preferences with this file?'))return;const ok=store.replace(x.preferences);loadFields();theme(prefs.theme);notice.textContent=ok?'Imported and saved.':'Imported for this page only: browser storage unavailable.';}catch(_){notice.textContent='Invalid preferences file; nothing changed.';}finally{file.value='';}});
    actions.append(button('Restore published defaults',()=>{if(!global.confirm('Reset all personal preferences and selections to published defaults?'))return;const ok=store.reset();loadFields();theme(prefs.theme);notice.textContent=ok?'Restored published defaults.':'Defaults restored for this page only.';}));
    transfer.append(actions);el.append(form,transfer);loadFields();notice.textContent=store.saved()?'Preferences ready. Changes are saved in this browser when you select Save preferences.':'Browser storage is unavailable or unreadable. Preferences may not persist.';
  }
  global.PulsePreferences={...api,load,base,node,link,split,button,theme};
  const main=async()=>{const el=document.getElementById('pulse-settings');try{const {data,store}=await load('data/preferences.json');theme(store.get().theme);if(el)settings(el,data,store);}catch(_){if(el)el.append(node('p','Preferences data unavailable. Refresh after the next website update.'));}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main);else main();
})(typeof window==='undefined'?globalThis:window);
