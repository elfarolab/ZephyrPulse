/* Exact-target hardware comparison, backed by browser-local preferences. */
((global)=>{
  'use strict';
  function metadata(target,baseline){
    if(baseline==='main')return target.metadata;
    const r=target.releases.find(x=>x.tag===baseline);
    return r?.found?{features:r.features,path:r.path,source_features:r.source_features,dts_evidence:r.dts_evidence}:null;
  }
  function state(target,feature,baseline){const m=metadata(target,baseline);return !m?'unknown':m.features.includes(feature)?'declared':(m.source_features||[]).includes(feature)?'source-evidence':(m.dts_evidence?.present_features||[]).includes(feature)?'source-present':'not-declared';}
  function coverage(target,requirements,baseline){const counts={declared:0,'not-declared':0,unknown:0};for(const f of requirements){const s=state(target,f,baseline);counts[s]=(counts[s]||0)+1;};return counts;}
  function sortTargets(a,b,req,baseline){const ca=coverage(a,req,baseline),cb=coverage(b,req,baseline);return matched(cb)-matched(ca)||cb.declared-ca.declared||ca.unknown-cb.unknown||a.target.localeCompare(b.target);}
  const matched=c=>c.declared+(c['source-evidence']||0);
  const api={metadata,state,coverage,sortTargets};
  if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
  const P=global.PulsePreferences;const {node,link,split,button}=P;
  const upstream='https://github.com/zephyrproject-rtos/zephyr';
  const urlSource=(ref,path)=>`${upstream}/blob/${encodeURIComponent(ref)}/${path.split('/').map(encodeURIComponent).join('/')}`;
  const states={'declared':'Declared','source-evidence':'DTS source hint','source-present':'Present in DTS; no okay hint','not-declared':'No evidence found','unknown':'No exact metadata'};
  const stateCell=(td,s)=>{td.className='pulse-state pulse-'+s;td.textContent=states[s];};
  function render(el,data,store){
    const catalog=data.comparison; if(!catalog){el.append(node('p','Comparator data unavailable; regenerate this site with v0.3.'));return;}
    const targets=catalog.targets, map=new Map(targets.map(t=>[t.id,t]));let prefs=store.get(),page=0,exactTarget='';
    const evidenceCache=new Map();let matrixEpoch=0;
    function loadEvidence(t){
      if(!t.evidence_url)return Promise.resolve(null); // old inline schema
      if(!/^data\/board-evidence\/[a-f0-9]{64}\.json$/.test(t.evidence_url))return Promise.reject(Error('Invalid evidence URL'));
      if(!evidenceCache.has(t.evidence_url)){
        const task=fetch(t.evidence_url).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{if(d.board_id!==t.board_id)throw Error('Evidence board mismatch');return d.targets;});
        evidenceCache.set(t.evidence_url,task);task.catch(()=>evidenceCache.delete(t.evidence_url));
      }
      return evidenceCache.get(t.evidence_url).then(d=>d[t.id]||null);
    }
    const query=new URLSearchParams(location.search).get('board');let linkedBoard=query&&targets.some(t=>t.board_id===query)?query:'';
    const title=node('p','Choose up to eight exact board / CPU targets. Rankings count YAML declarations and DTS source hints, not verified support; they are not a hardware-quality score.');
    const notice=node('p');notice.setAttribute('role','status');
    const persist=patch=>{const ok=store.update(patch);prefs=store.get();notice.textContent=ok?'Preferences saved in this browser.':'Browser storage unavailable: changes apply only on this page.';};
    const form=node('div');form.className='pulse-filter';
    const field=(title,control)=>{const label=node('label',title);label.append(control);form.append(label);return control;};
    const req=node('input');req.value=prefs.requirements.join(', ');req.placeholder='ethernet, can-fd, usb, crypto';field('Required capability identifiers',req);
    const reqAdd=node('select');const empty=node('option','Add a known capability…');empty.value='';reqAdd.append(empty);for(const f of catalog.features){const o=node('option',f);o.value=f;reqAdd.append(o);}field('Known capability names',reqAdd);
    const baseline=node('select');for(const [v,t] of [['main','Main branch'],...catalog.snapshots.map(s=>[s.tag,`${s.tag} — ${s.latest_stable?'latest stable; ':''}${s.lts?'configured LTS; ':''}${s.lifecycle}`])]){const o=node('option',t);o.value=v;baseline.append(o);}
    if(![...baseline.options].some(o=>o.value===prefs.baseline)){const o=node('option',prefs.baseline+' — unavailable in this snapshot');o.value=prefs.baseline;baseline.append(o);}baseline.value=prefs.baseline;field('Compare source metadata at',baseline);
    const rows=node('select');for(const [v,t] of [['all','All relevant capabilities'],['required','Required capabilities'],['differences','Differences + required']]){const o=node('option',t);o.value=v;rows.append(o);}rows.value=prefs.comparison_rows;field('Matrix rows',rows);
    const search=node('input');search.type='search';search.placeholder='*mcxn*, ra8P1, cortex, nxp';search.value=linkedBoard?'':prefs.search;field('Find boards, SoCs, vendors or targets',search);
    const chk=node('input');chk.type='checkbox';chk.checked=linkedBoard?false:prefs.matches_only;field('Only targets with evidence for every requirement',chk);
    const picked=node('div');picked.className='pulse-picked';const matrix=node('div');matrix.className='pulse-matrix';const discovery=node('div');discovery.className='pulse-matrix';const desc=node('p');
    const pageActions=node('div');pageActions.className='pulse-actions';const pageLabel=node('span');const clearLinked=button('Clear linked filter',()=>{linkedBoard='';exactTarget='';page=0;drawDiscovery();});clearLinked.className='pulse-active-filter';form.append(clearLinked);
    const prev=button('Previous',()=>{page--;drawDiscovery();});const next=button('Next',()=>{page++;drawDiscovery();});pageActions.append(prev,pageLabel,next);
    const requirements=()=>[...new Set(split(req.value).map(x=>x.toLowerCase()))].slice(0,200);
    // Same glob semantics as Python fnmatch for common patterns, including bracket classes.
    function match(value,term){value=String(value??'').toLowerCase();term=term.toLowerCase();if(!/[*?\[]/.test(term))return value.includes(term);let out='^';for(let i=0;i<term.length;i++){const c=term[i];if(c==='*')out+='.*';else if(c==='?')out+='.';else if(c==='['){let j=term.indexOf(']',i+1);if(j>i+1){let cl=term.slice(i+1,j);if(cl[0]==='!')cl='^'+cl.slice(1);else if(cl[0]==='^')cl='\\'+cl;out+='['+cl.replace(/\\/g,'\\\\')+']';i=j;}else out+='\\[';}else out+=c.replace(/[\\^$.*+?()[\]{}|]/g,'\\$&');}try{return new RegExp(out+'$','s').test(value);}catch(_){return false;}}
    function table(headers){const t=node('table');t.className='pulse-compare-table';const head=node('thead'),r=node('tr');for(const h of headers){const th=node('th');th.scope='col';if(typeof h==='string')th.textContent=h;else th.append(h);r.append(th);}head.append(r);t.append(head);const body=node('tbody');t.append(body);return [t,body];}
    function appendRow(body,name,values){const tr=node('tr'),th=node('th',name);th.scope='row';tr.append(th);for(const v of values){const td=node('td');if(typeof v==='string'||typeof v==='number')td.textContent=v;else if(v)td.append(v);tr.append(td);}body.append(tr);return tr;}
    const choose=id=>{if(prefs.selected.includes(id))return;if(prefs.selected.length>=8){notice.textContent='Maximum eight targets. Remove one first.';return;}persist({selected:[...prefs.selected,id]});draw();};
    const remove=id=>{persist({selected:prefs.selected.filter(x=>x!==id)});draw();};
    function drawMatrix(){
      const epoch=++matrixEpoch;
      picked.replaceChildren();matrix.replaceChildren();picked.append(node('p',`${prefs.selected.length} / 8 selected targets`));
      for(const id of prefs.selected){const t=map.get(id);const chip=node('span',t?t.target:id+' (missing from current catalog)');chip.append(button('Remove',()=>remove(id)));picked.append(chip);}
      if(prefs.selected.length)picked.append(button('Clear comparison',()=>{persist({selected:[]});draw();}));
      const chosen=prefs.selected.map(id=>map.get(id)).filter(Boolean);if(!chosen.length){matrix.append(node('p','Add targets from the discovery table below. Unknown saved targets can be removed above.'));return;}
      const bs=baseline.value,required=requirements();const [t,b]=table(['Evidence',...chosen.map(x=>link(x.target,x.url))]);
      appendRow(b,'Board / vendor',chosen.map(x=>`${x.name} · ${x.vendor_name}`));appendRow(b,'Board-listed SoCs (not target mapping)',chosen.map(x=>x.socs.join(', ')||'Not declared'));
      appendRow(b,'Metadata source',chosen.map(x=>{const m=metadata(x,bs);if(!m)return 'No exact metadata at this baseline';const a=node('a','View YAML evidence');a.href=urlSource(bs==='main'?(x.evidence_revision||data.head):bs,m.path);return a;}));
      appendRow(b,'Architecture (main)',chosen.map(x=>x.metadata?.arch||'Not declared'));
      appendRow(b,'RAM (main metadata, normally KiB)',chosen.map(x=>String(x.metadata?.ram??'Not declared')));
      appendRow(b,'Flash (main metadata, normally KiB)',chosen.map(x=>String(x.metadata?.flash??'Not declared')));
      appendRow(b,'Required features with evidence',chosen.map(x=>{const c=coverage(x,required,bs);return required.length?`${matched(c)}/${required.length} with evidence · ${c.declared} YAML · ${c['source-evidence']||0} DTS hints`:'No requirements selected';}));
      const core=P.defaults.requirements;const standard=['gpio','uart','i2c','spi','adc','dac','pwm','can','can-fd','watchdog','counter','rtc','usb','usb-device','usb-host','ethernet','wifi','bluetooth','bluetooth-le','i2s','pdm','dma','flash','sdhc','display','sensor','crypto','power-management','low-power'];
      let features=[...new Set([...required,...standard,...core,...chosen.flatMap(x=>[...(metadata(x,bs)?.features||[]),...(metadata(x,bs)?.source_features||[])])])];
      if(rows.value==='required')features=features.filter(f=>required.includes(f));if(rows.value==='differences')features=features.filter(f=>required.includes(f)||new Set(chosen.map(x=>state(x,f,bs))).size>1);
      const featureRows=[];for(const f of features){const tr=appendRow(b,(required.includes(f)?'Required · ':'')+f,chosen.map(()=>''));featureRows.push(tr);chosen.forEach((x,i)=>{const td=tr.children[i+1];stateCell(td,state(x,f,bs));const ev=metadata(x,bs)?.dts_evidence?.nodes||[];appendEvidence(td,x,f,ev,bs);});}
      function appendEvidence(td,x,f,ev,bs){for(const e of ev.filter(e=>e.features.includes(f))){const a=node('a',e.compatible);a.href=urlSource(bs==='main'?(x.evidence_revision||data.head):bs,e.compatible_paths[0]);td.append(node('br'),a);if(e.status_paths?.length){const status=node('a','status');status.href=urlSource(bs==='main'?(x.evidence_revision||data.head):bs,e.status_paths.at(-1));td.append(node('span',' · '),status);}}}
      // Keep coverage usable immediately. Only selected boards load full evidence.
      const detailStatus=node('p','Loading source evidence for selected targets…');
      detailStatus.setAttribute('role','status');
      if(chosen.some(x=>x.evidence_url)){matrix.append(detailStatus);
        Promise.allSettled(chosen.map(loadEvidence)).then(results=>{
          if(epoch!==matrixEpoch)return;
          let errors=0;results.forEach((result,i)=>{if(result.status!=='fulfilled'){errors++;return;}const x=chosen[i];if(!x.evidence_url)return;const ev=result.value?.[bs];if(!ev){if(metadata(x,bs))errors++;return;}features.forEach((f,j)=>appendEvidence(featureRows[j].children[i+1],x,f,ev.nodes||[],bs));});
          detailStatus.textContent=errors?'Some detailed evidence could not be loaded. Board profiles and YAML links remain available.':'Source evidence loaded for selected targets.';
        });
      }
      for(const s of catalog.snapshots){appendRow(b,`${s.tag} exact metadata · ${s.lts?'LTS-configured; ':''}${s.lifecycle}`,chosen.map(x=>{const r=x.releases.find(r=>r.tag===s.tag);if(!r?.found)return 'Not found at current metadata path / identifier';const c=coverage(x,required,s.tag);return required.length?`${matched(c)}/${required.length} with evidence`:'Exact metadata found';}));}
      appendRow(b,'Last board-level milestone (UTC)',chosen.map(x=>x.last_milestone?.slice(0,10)||'None in retained history'));appendRow(b,'Retained board-level milestones',chosen.map(x=>x.milestone_count));appendRow(b,'Vendor attributed commits (history)',chosen.map(x=>String(x.vendor_commits??'No attributed data')));appendRow(b,'Vendor last activity (UTC)',chosen.map(x=>x.vendor_last?.slice(0,10)||'No attributed data'));
      matrix.append(t);const notes=node('p','Declared = exact target YAML lists the capability. DTS source hint = a matching compatible with an okay or default-status hint in the target include graph; conditions, parent state, overrides and Kconfig are not resolved. No evidence found does not mean unsupported. No exact metadata = unknown. Release comparison checks the same current metadata path and target identifier, so old layouts and renamed targets can be missed. RAM/flash and architecture are main-branch metadata regardless of baseline. Board milestones and vendor history are context, not target-level verification.');matrix.append(notes);
    }
    function drawDiscovery(){
      const terms=split(search.value);const required=requirements(),bs=baseline.value;let found=targets.filter(t=>(!linkedBoard||t.board_id===linkedBoard)&&(!exactTarget||t.target===exactTarget)&&(!terms.length||terms.some(p=>[t.board,t.name,t.vendor,t.vendor_name,t.target,t.board_id,...t.socs,t.metadata?.arch].some(v=>match(v,p))))&&(!chk.checked||matched(coverage(t,required,bs))===required.length));
      clearLinked.hidden=!linkedBoard&&!exactTarget;clearLinked.textContent=(exactTarget||linkedBoard)+' ×';found.sort((a,b)=>sortTargets(a,b,required,bs));const size=40;const pages=Math.max(1,Math.ceil(found.length/size));page=Math.max(0,Math.min(page,pages-1));desc.textContent=`${found.length} of ${targets.length} targets · ${data.coverage.complete?'Complete':'Partial'} history backfill · sorted by evidence count`;pageLabel.textContent=`Page ${page+1} / ${pages}`;prev.disabled=page===0;next.disabled=page>=pages-1;
      const [t,b]=table(['Exact target','Vendor / SoCs','Requirements with evidence','Action']);for(const x of found.slice(page*size,(page+1)*size)){const c=coverage(x,required,bs);const add=button(prefs.selected.includes(x.id)?'Selected':'Add',()=>choose(x.id));add.disabled=prefs.selected.includes(x.id);const action=node('span');action.append(add,' ',link('Board profile',x.url));const assoc=node('span');assoc.append(link(x.vendor_name,'boards.html?vendor='+encodeURIComponent(x.vendor)));for(const soc of x.socs)assoc.append(' · ',link(soc,'boards.html?subject='+encodeURIComponent(soc)));const tr=appendRow(b, x.target,[assoc,required.length?`${matched(c)}/${required.length} · ${c['source-evidence']||0} DTS hints`:'No requirements',action]);const toggle=button(x.target,()=>{exactTarget=exactTarget===x.target?'':x.target;page=0;drawDiscovery();});toggle.className='pulse-subject-button';tr.firstElementChild.replaceChildren(toggle);}discovery.replaceChildren(t);if(!found.length)discovery.append(node('p','No matching targets. Clear the search or disable the requirements filter.'));
    }
    function draw(){drawMatrix();drawDiscovery();}
    const changed=()=>{persist({requirements:requirements(),baseline:baseline.value,comparison_rows:rows.value,search:search.value,matches_only:chk.checked});page=0;draw();};
    req.addEventListener('input',changed);reqAdd.addEventListener('change',()=>{if(reqAdd.value){req.value=[...new Set([...requirements(),reqAdd.value])].join(', ');reqAdd.value='';changed();}});baseline.addEventListener('change',changed);rows.addEventListener('change',changed);search.addEventListener('input',changed);chk.addEventListener('change',changed);
    el.append(title,form,notice,node('h2','Selected targets'),picked,matrix,node('h2','Discover and add hardware'),desc,discovery,pageActions);
    if(!store.saved())notice.textContent='Browser storage unavailable: selections may not persist.';draw();
  }
  const main=async()=>{const el=document.getElementById('pulse-comparator');if(!el)return;try{const {data,store}=await P.load();render(el,data,store);}catch(e){console.error(e);el.append(node('p','Comparator unavailable. The static board profiles remain accessible.'));}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main);else main();
})(typeof window==='undefined'?globalThis:window);
