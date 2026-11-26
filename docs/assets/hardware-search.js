/* Generator-independent structured search. No third-party libraries or remote queries. */
((global)=>{
  'use strict';
  const upstream='https://github.com/zephyrproject-rtos/zephyr';
  const array=x=>Array.isArray(x)?x:[];
  const split=v=>String(v||'').split(',').map(s=>s.trim()).filter(Boolean);
  function pattern(value,term){
    value=String(value??'').toLowerCase();term=String(term??'').trim().toLowerCase();if(!term)return false;
    if(!/[*?\[]/.test(term))return value.includes(term);
    // Dynamic programming for glob matching; no regex backtracking on user input.
    let tokens=[];
    for(let i=0;i<term.length;i++){
      const c=term[i];
      if(c==='*'){if(tokens.at(-1)?.type!=='star')tokens.push({type:'star'});}
      else if(c==='?')tokens.push({type:'any'});
      else if(c==='['){let j=term.indexOf(']',i+1);if(term[i+1]==='!'||term[i+1]==='^')j=term.indexOf(']',i+2);
        if(j>i+1){let cls=term.slice(i+1,j);let neg=cls.startsWith('!');if(neg)cls=cls.slice(1);const ranges=[];for(let k=0;k<cls.length;k++){if(k+2<cls.length&&cls[k+1]==='-'){ranges.push([cls[k],cls[k+2]]);k+=2;}else ranges.push([cls[k],cls[k]]);}tokens.push({type:'class',ranges,neg});i=j;}
        else tokens.push({type:'char',c});
      }else tokens.push({type:'char',c});
    }
    let prev=new Uint8Array(value.length+1);prev[0]=1;
    for(const t of tokens){const next=new Uint8Array(value.length+1);if(t.type==='star'){next[0]=prev[0];for(let j=1;j<=value.length;j++)next[j]=prev[j]||next[j-1];}
      else for(let j=1;j<=value.length;j++){const c=value[j-1];let hit=t.type==='any'||(t.type==='char'&&c===t.c)||(t.type==='class'&&(t.ranges.some(([a,b])=>a<=c&&c<=b)!==t.neg));next[j]=prev[j-1]&&hit;}prev=next;
    }return !!prev[value.length];
  }
  const any=(values,terms)=>values.some(v=>terms.some(t=>pattern(v,t)));
  const fields=b=>b?[b.name,b.full_name,b.folder,...array(b.socs),...array(b.targets)]:[];
  const vendors=b=>b?[b.vendor,b.vendor_name].filter(Boolean):[];
  function records(data){
    const boards=new Map(array(data.boards).map(b=>[b.id,b]));const result=[];
    for(const t of array(data.comparison?.targets)){
      const b=boards.get(t.board_id);const fs=[...new Set([...array(t.metadata?.features),...array(t.metadata?.source_features)])];
      result.push({kind:'target',title:t.target,detail:`${t.name||t.board} · ${t.vendor_name||t.vendor} · ${t.metadata?fs.join(', ')||'No positive capability evidence':'No exact target metadata'}`,url:t.url,compare:'compare.html?board='+encodeURIComponent(t.board_id),date:null,vendors:[t.vendor,t.vendor_name].filter(Boolean),features:fs,boardFields:[t.board,t.name,t.target,...array(t.socs),...fields(b)],terms:[t.id,t.target,t.board,t.name,t.metadata?.path,...array(t.socs),...fs,...fields(b)],release:array(t.releases).filter(r=>r.found).map(r=>r.tag).join(', '),confidence:t.metadata?'YAML / DTS source evidence':'Unknown metadata'});
    }
    for(const e of array(data.events)){
      const associated=array(e.boards).map(id=>boards.get(id)).filter(Boolean);const text=[e.subject,e.detail,e.path,e.commit_subject,e.sha];
      result.push({kind:e.kind,title:e.subject,detail:e.detail,url:upstream+'/commit/'+e.sha,date:e.committed?.slice(0,10),vendors:[...new Set(associated.flatMap(vendors))],features:[],boardFields:[...text,...associated.flatMap(fields)],terms:[...text,...associated.flatMap(fields)],release:e.release?.first_release|| (e.release?.status==='main_only'?'Main only (exact commit)':''),confidence:e.confidence||'',source:e.path?upstream+'/blob/'+e.sha+'/'+e.path.split('/').map(encodeURIComponent).join('/'):null});
    }
    for(const p of array(data.pull_requests?.items)){
      result.push({kind:'pr',title:`#${p.number} — ${p.title}`,detail:array(p.labels).join(', '),url:upstream+'/pull/'+p.number,date:p.updated?.slice(0,10),vendors:[],features:[],boardFields:[p.title,...array(p.labels)],terms:[p.title,String(p.number),...array(p.labels)],release:'Not merged',confidence:(p.draft?'Draft PR':'Open PR')+(data.pull_requests.status==='stale'?' · stale snapshot':'')});
    }
    for(const v of array(data.vendors)) result.push({kind:'vendor',title:v.vendor,detail:`${v.commits} attributed hardware commits in retained history`,url:'vendors.html',date:v.last?.slice(0,10),vendors:[v.vendor],features:[],boardFields:[],terms:[v.vendor],release:'',confidence:'Activity signal'});
    for(const r of array(data.releases))result.push({kind:'release',title:r.tag,detail:`${r.series||''}${r.lts?' · Configured LTS':''}`,url:'releases.html',date:null,vendors:[],features:[],boardFields:[],terms:[r.tag,r.series,r.lts?'lts':'stable'],release:r.tag,confidence:'Git tag'});
    return result;
  }
  function watched(r,prefs){return any(r.boardFields,array(prefs.boards))||any([...r.vendors,...(r.kind==='target'?[]:r.terms)],array(prefs.vendors))||any([...r.features,...r.terms],array(prefs.peripherals));}
  function filter(rows,prefs){
    const queries=split(prefs.hardware_query), vendor=split(prefs.hardware_vendor), caps=split(prefs.hardware_capability).map(s=>s.toLowerCase());
    const kind=prefs.hardware_kind||'all', from=prefs.hardware_from||'', to=prefs.hardware_to||'';
    return rows.filter(r=>{
      if(kind!=='all'&&r.kind!==kind)return false;
      if(queries.length&&!any([r.title,r.detail,r.kind,r.release,...r.terms,...r.vendors],queries))return false;
      if(vendor.length&&!any(r.vendors,vendor))return false;
      if(caps.length&&(r.kind!=='target'||!caps.every(c=>r.features.some(f=>/[*?\[]/.test(c)?pattern(f,c):f.toLowerCase()===c))))return false;
      if((from||to)&&(!r.date||(from&&r.date<from)||(to&&r.date>to)))return false;
      if(prefs.hardware_watched&&!watched(r,prefs))return false;
      return true;
    });
  }
  const api={pattern,records,filter,watched};
  if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
  const P=global.PulsePreferences;const {node,link,button}=P;
  const kinds={all:'All results',target:'Exact board targets',board_feature:'Board capability changes',board_candidate:'Possible board support',board:'New boards',sensor:'Sensors',driver:'Drivers',soc:'SoCs',dts:'Devicetree',docs:'Documentation',other:'Other changes',pr:'Upcoming PRs',vendor:'Vendor activity',release:'Release tags'};
  async function main(){const el=document.getElementById('pulse-hardware-search');if(!el)return;
    try{const {data,store}=await P.load();const all=records(data);let page=0,timer;const linkedSubject=new URLSearchParams(location.search).get('subject');let temporary=!!linkedSubject;const controls={};const form=node('form');form.className='pulse-filter';form.addEventListener('submit',e=>e.preventDefault());
      function field(key,title,type,opts){const label=node('label',title);let input;if(type==='select'){input=node('select');for(const [v,t] of opts){const o=node('option',t);o.value=v;input.append(o);}}else{input=node('input');input.type=type;if(type==='search')input.maxLength=512;}controls[key]=input;label.append(input);form.append(label);return input;}
      field('hardware_query','Find hardware or news (comma = OR)','search').placeholder='*mcxn*, ra8P1';field('hardware_kind','Result type','select',Object.entries(kinds));field('hardware_vendor','Attributed vendor','search').placeholder='nxp, renesas';field('hardware_capability','Target capabilities with evidence (all terms)','search').placeholder='ethernet, can-fd';field('hardware_from','Date from (UTC)','date');field('hardware_to','Date through (UTC)','date');field('hardware_watched','Only my watchlist','checkbox');
      const note=node('p','Dates apply only to dated results. Capability filters match current exact-target YAML declarations and DTS source hints, not verified support or PR claims. Vendor filtering uses board associations; unassigned news is excluded when a vendor is selected.');
      const status=node('p');status.setAttribute('role','status');const notice=node('p');notice.setAttribute('role','status');const list=node('div');const pager=node('div');pager.className='pulse-actions';const pageLabel=node('span');const prev=button('Previous',()=>{page--;draw();}),next=button('Next',()=>{page++;draw();});pager.append(prev,pageLabel,next);
      const read=()=>Object.fromEntries(Object.entries(controls).map(([k,c])=>[k,c.type==='checkbox'?c.checked:c.value]));
      const apply=()=>{const p=store.get();for(const [k,c] of Object.entries(controls)){if(c.type==='checkbox')c.checked=p[k];else c.value=p[k]??'';}};
      function draw(){const p={...store.get(),...read()};let rows=filter(all,p);rows.sort((a,b)=>{if(a.kind==='target'&&b.kind!=='target')return -1;if(b.kind==='target'&&a.kind!=='target')return 1;return (b.date||'').localeCompare(a.date||'')||a.title.localeCompare(b.title);});
        const max=Math.max(0,Math.ceil(rows.length/50)-1);page=Math.min(Math.max(0,page),max);status.textContent=`${rows.length} matching results · ${data.updated||'snapshot time unknown'}`;list.replaceChildren();if(!rows.length)list.append(node('p','No matches. Try clearing filters.'));
        for(const r of rows.slice(page*50,(page+1)*50)){const card=node('article');card.className='pulse-search-result';const title=node('h3');title.append(link(r.title,r.url));card.append(title,node('p',[kinds[r.kind]||r.kind,r.date,r.confidence,r.release,watched(r,p)?'Watchlist match':''].filter(Boolean).join(' · ')),node('p',r.detail||''));if(r.compare)card.append(link('Compare this board',r.compare));if(r.source)card.append(link('Source evidence',r.source));if(Object.hasOwn(kinds,r.kind)&&!['target','pr','vendor','release','all'].includes(r.kind))card.append(' · ',link('Open filtered category',r.kind+'.html?subject='+encodeURIComponent(r.title)));list.append(card);}
        prev.disabled=page===0;next.disabled=page===max;pageLabel.textContent=`Page ${page+1} of ${max+1}`;
      }
      const change=()=>{page=0;clearTimeout(timer);const ok=temporary?false:store.update(read());notice.textContent=temporary?'Temporary linked search; saved preferences unchanged.':ok?'Filters saved in this browser.':'Browser storage unavailable; filters apply on this page only.';timer=setTimeout(draw,120);};
      for(const c of Object.values(controls))c.addEventListener(c.type==='search'?'input':'change',change);
      form.append(button('Clear filters',()=>{for(const [k,c] of Object.entries(controls)){if(c.type==='checkbox')c.checked=false;else c.value=k==='hardware_kind'?'all':'';}change();}));
      el.append(form,note,link('Personal settings','settings.html'),notice,status,list,pager);apply();if(temporary){for(const [k,c] of Object.entries(controls)){if(c.type==='checkbox')c.checked=false;else c.value=k==='hardware_kind'?'all':'';}controls.hardware_query.value=linkedSubject;notice.textContent='Temporary linked search; saved preferences unchanged.';const restore=button('Restore saved search',()=>{temporary=false;apply();page=0;notice.textContent='Restored saved search.';restore.remove();draw();});form.append(restore);}draw();
    }catch(error){el.append(node('p','Hardware search unavailable. Use the static page links below or refresh after the next update.'));}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main);else main();
})(typeof window==='undefined'?globalThis:window);
