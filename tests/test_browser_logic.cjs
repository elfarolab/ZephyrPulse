const assert=require('node:assert/strict');
const {test}=require('node:test');
const P=require('../docs/assets/preferences.js');
const C=require('../docs/assets/comparator.js');
const mem=(initial={})=>({data:{...initial},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=v}});
test('browser overrides YAML including empty values and persists on reload',()=>{
 const s=mem(),data={watchlist:{boards:['*mcxn*'],vendors:['nxp']},preferences:{requirements:['can'],home_limit:12}};
 const a=P.create(data,s);assert.deepEqual(a.get().boards,['*mcxn*']);assert.equal(a.get().home_limit,12);
 a.update({boards:[],requirements:['can-fd'],home_limit:3,selected:['a']});
 const b=P.create({watchlist:{boards:['ra8p1'],vendors:['renesas']},preferences:{home_limit:20}},s);
 assert.deepEqual(b.get().boards,[]);assert.deepEqual(b.get().vendors,['renesas']);assert.deepEqual(b.get().selected,['a']);assert.equal(b.get().home_limit,3);
 b.reset();assert.deepEqual(b.get().boards,['ra8p1']);assert.equal(b.get().home_limit,20);
});
test('migrate v2 watchlist, validate imports, preserve explicit false',()=>{
 const s=mem({'zephyr-pulse-watchlist-v2':JSON.stringify({boards:['RA8P1'],vendors:[],peripherals:[]})});
 const a=P.create({},s);assert.deepEqual(a.get().boards,['RA8P1']);
 a.update({matches_only:false,home_limit:-1,comparison_rows:'invalid',selected:Array.from({length:10},(_,i)=>String(i))});
 assert.equal(a.get().selected.length,8);assert.equal(a.get().home_limit,8);assert.equal(a.get().comparison_rows,'all');
 const b=P.create({},mem());b.replace(a.export().preferences);assert.deepEqual(b.get(),a.get());
});
test('blocked storage keeps page-local preferences and reports failure',()=>{
 const a=P.create({},undefined);assert.equal(a.saved(),false);assert.equal(a.update({boards:['*mcxn*']}),false);assert.deepEqual(a.get().boards,['*mcxn*']);
});
test('exact target evidence and unknown vs not declared',()=>{
 const a={target:'a',metadata:{features:['can','usb-device']},releases:[{tag:'v4.0.0',found:true,features:['can']}]};
 const b={target:'b',metadata:null,releases:[]};
 assert.equal(C.state(a,'can-fd','main'),'not-declared');assert.equal(C.state(a,'usb-host','main'),'not-declared');assert.equal(C.state(b,'can','main'),'unknown');
 assert.equal(C.state(a,'usb-device','v4.0.0'),'not-declared');assert.equal(C.state(a,'can','v3.7.0'),'unknown');
 assert.deepEqual(C.coverage(a,['can','can-fd'],'main'),{declared:1,'not-declared':1,unknown:0});assert.equal([b,a].sort((x,y)=>C.sortTargets(x,y,['can'],'main'))[0],a);
});
test('DTS hints stay separate from declarations and disabled-only evidence',()=>{
 const t={target:'cpu0',metadata:{features:['can'],source_features:['can','can-fd'],dts_evidence:{present_features:['can','can-fd','usb-host']}},releases:[{tag:'v4',found:true,features:['can'],source_features:[],dts_evidence:{present_features:['can-fd']}}]};
 assert.equal(C.state(t,'can-fd','main'),'source-evidence');assert.equal(C.state(t,'can-fd','v4'),'source-present');assert.equal(C.state(t,'usb-host','main'),'source-present');assert.equal(C.state(t,'can','main'),'declared');
 assert.deepEqual(C.coverage(t,['can','can-fd','usb-host'],'main'),{declared:1,'not-declared':0,unknown:0,'source-evidence':1,'source-present':1});
});
