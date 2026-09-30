/**
 * tests/ui-smoke.js - dev only, no dependencies:  node tests/ui-smoke.js [chart]
 *
 * Runs js/ui/*.js against a tiny fake DOM (tests/fake-dom.js), builds
 * every copied component in every state, clicks every button, changes every
 * input and opens every overlay. Exits 1 on any error. `chart` adds a fake
 * Chart.js to exercise the chart wrapper.
 */
const vm=require('vm'),fs=require('fs'),path=require('path');
const ROOT=path.join(__dirname,'..');
const { win, doc, flush, tick } = require('./fake-dom')({ ids: ['kitRoot', 'toasts', 'dialogHost'] });
let charts=0,destroyed=0;
if(process.argv[2]==='chart'){win.Chart=function(canvas,cfg){charts++;this.cfg=cfg;
  const fakeCtx={createLinearGradient:()=>({addColorStop(){}})};
  const chartObj={chartArea:{left:0,right:100,top:0,bottom:100},ctx:fakeCtx,canvas,scales:{y:{getPixelForValue:()=>50}},getDatasetMeta:()=>({data:[{getProps:()=>({y:1})}]})};
  cfg.data.datasets.forEach(d=>['backgroundColor','hoverBackgroundColor'].forEach(k=>{if(typeof d[k]==='function'){d[k]({chart:chartObj});d[k]({chart:{chartArea:null}})}}));
  const ext=cfg.options.plugins.tooltip.external;
  ext({chart:chartObj,tooltip:{opacity:1,caretX:5,caretY:5,title:['t'],dataPoints:[{dataset:cfg.data.datasets[0],dataIndex:0,raw:3,formattedValue:'3',label:'a'}]}});
  ext({chart:chartObj,tooltip:{opacity:0}});
  if(cfg.options.onClick)cfg.options.onClick({},[{index:0,datasetIndex:0}],this);
  if(cfg.options.onHover)cfg.options.onHover({},[]);
  this.destroy=()=>destroyed++;};}const ctx=vm.createContext(win);
vm.runInContext(fs.readFileSync(path.join(ROOT,'js/themes.js'),'utf8'),ctx,{filename:'themes.js'});
['core','components','glyphs','overlays','charts'].forEach(f=>vm.runInContext(fs.readFileSync(path.join(ROOT,'js/ui/'+f+'.js'),'utf8'),ctx,{filename:'ui/'+f+'.js'}));
let errs=0;
function check(name,fn){try{fn();flush()}catch(e){errs++;console.log('ERR',name,e.stack.split('\n').slice(0,3).join(' | '))}}
function expect(name,cond){if(!cond){errs++;console.log('FAIL',name)}}
const ui=win.QVM.ui, root=doc.getElementById('kitRoot');
const put=n=>{root.appendChild(n.node||n);return n};

// every component, every state
check('panel',()=>{['ok','warning','critical','expired','blocked',null].forEach(s=>{const p=put(ui.panel({title:'T',icon:'settings',status:s,glow:true,actions:[ui.button('A')],body:ui.el('p',{text:'x'})}));p.setStatus('critical')})});
check('buttons',()=>{[undefined,'primary','danger','ghost'].forEach(k=>['sm',undefined,'lg'].forEach(z=>put(ui.button('B',{kind:k,size:z,icon:'plus',onClick(){}}))));put(ui.button('Off',{disabled:true}))});
check('segmented',()=>{const s=put(ui.segmented({label:'Theme',value:'a',options:[{value:'a',label:'A',icon:'sun'},{value:'b',label:'B'},{value:'c',label:'C',disabled:true}],onChange(){}}));s.set('b');expect('seg value',s.value()==='b')});
check('toggle',()=>{put(ui.toggle({label:'Check',checked:true,onChange(){}}));put(ui.toggle({kind:'switch',label:'Switch',onChange(){}}))});
check('field',()=>{const f=put(ui.field({label:'Cut depth',type:'number',unit:'µm',hint:'0-50'}));f.setState('valid','ok');f.setState('invalid','too deep');f.setState(null);
  put(ui.field({label:'Tool',options:[{value:'a',label:'A'}],value:'a'}));put(ui.field({label:'Purpose',multiline:true,value:'x'}));put(ui.field({label:'Off',disabled:true}))});
check('form',()=>{const f=put(ui.form([{key:'code',label:'Code',kind:'text'},{key:'n',label:'Level',kind:'number',unit:'µm',cls:'half'},
  {key:'type',label:'Type',kind:'select',options:[{value:'a',label:'A'},{value:'b',label:'B'}]},{key:'unit',label:'Unit',kind:'text',showIf:v=>v.type==='b'},
  {key:'req',label:'Required',kind:'check'},{key:'days',label:'Days',kind:'checks',options:[{value:1,label:'Mon'},{value:2,label:'Tue'}]},
  {key:'txt',label:'Notes',kind:'longtext'}],{code:'QVM',n:5,type:'a',days:[2]}));
  expect('form values',JSON.stringify(f.values())===JSON.stringify({code:'QVM',n:5,type:'a',unit:'',req:false,days:[2],txt:''}));
  expect('showIf hides',f.node.children[3].hidden===true);
  f.node.children[2].querySelector('select').value='b';f.node.dispatch('change');expect('showIf shows',f.node.children[3].hidden===false);
  f.node.children[1].querySelector('input').value='abc';expect('a bad number is NaN',isNaN(f.values().n));
  f.node.children[1].querySelector('input').value='';expect('an empty number is null',f.values().n===null);
  f.setError('code','Taken');expect('setError marks the field',f.node.children[0].classList.contains('is-invalid'));f.clearErrors();f.setError('days','Pick one');f.focus()});
check('chips+leds',()=>{['ok','warning','critical','expired','blocked','neutral',{expired:true},{blocked:true},{status:'ok'}].forEach(s=>{root.appendChild(ui.statusChip(s));root.appendChild(ui.led(s,'x'))});
  expect('displayStatus expired wins',ui.displayStatus({expired:true,blocked:true})==='expired')});
check('kpi',()=>{['ok','critical','expired',undefined].forEach(s=>{const k=put(ui.kpiTile({label:'Open',value:12,status:s,icon:'inbox',sub:'s',href:'#/x'}));k.update(0,'none')})});
check('table',()=>{root.appendChild(ui.el('table',{class:'grid'},[ui.el('tr',{},[ui.el('th',{text:'h'})])]))});
check('tabs',()=>{const t=put(ui.tabs([{key:'a',label:'A',icon:'user'},{key:'b',label:'B'}],()=>{}));t.setActive('b');expect('tabs active',t.node.querySelector('.tab-btn.active').textContent==='B')});
check('empty+skeleton',()=>{put(ui.emptyState({icon:'inbox',title:'None',text:'t',actionLabel:'Add',onAction(){}}));put(ui.skeleton(4))});
check('glyphs',()=>{expect('seven glyphs',ui.GLYPHS.length===7);
  ui.GLYPHS.forEach(g=>['idle','live','maint','off'].forEach(s=>{const n=ui.toolGlyph(g.key,{size:40,state:s,label:g.label});root.appendChild(n);
    expect('glyph '+g.key+' '+s,n.classList.contains('is-'+s)&&n.innerHTML.indexOf('tg-body')!==-1&&n.getAttribute('role')==='img')}));
  const d=ui.toolGlyph('xyz');expect('unknown glyph -> generic',d.dataset.glyph==='generic'&&d.getAttribute('aria-hidden')==='true')});
check('icons',()=>{['logo','inbox','analytics','settings','help'].forEach(n=>{const i=ui.icon(n);expect('icon '+n,i.innerHTML.length>10)})});
check('format',()=>{expect('formatTs',ui.formatTs('2026-09-24T08:05:00Z')==='24.09.2026 10:05');expect('duration',ui.formatDurationH(1.5)==='1 h 30 min')});
check('esc',()=>{expect('esc',ui.esc('<b a="1">&')==='&lt;b a=&quot;1&quot;&gt;&amp;')});
check('charts',()=>{const c=ui.chart(t=>({type:'bar',data:{labels:['a','b'],datasets:[{label:'x',data:[1,2],backgroundColor:t.color('accent')}]},options:{}}),{height:200,expand:true,onPick(){}});root.appendChild(c.node);c.refresh&&c.refresh()});

// overlays: toasts, dialogs, menu, tooltip
check('toasts',()=>{['info','success','warning','error'].forEach(k=>ui.toast({message:'m',kind:k,actions:[{label:'Retry',onClick(){}}]}));ui.toastError('boom',null)});
check('dialogs',()=>{ui.dialog({title:'D',icon:'info',body:ui.el('p',{text:'b'})});ui.confirm({message:'sure?',danger:true})});
check('menu',()=>{const a=ui.el('button');root.appendChild(a);ui.menu(a,[{label:'One',icon:'user',aside:'?',onClick(){}}])});
check('tips',()=>{const box=ui.el('div',{},[ui.el('span',{class:'tipme',text:'t'})]);root.appendChild(box);ui.bindTips(box,'.tipme',()=>ui.tipRow('a','b'));box.querySelector('.tipme').dispatch('mouseover');box.querySelector('.tipme').dispatch('mouseout')});

// click every button, change every input
let clicked=0;
for(const b of root.querySelectorAll('button')){check('click '+b.textContent,()=>{b.dispatch('click');clicked++})}
for(const b of doc.getElementById('dialogHost').querySelectorAll('button')){check('dialog button',()=>b.dispatch('click'))}
for(const i of root.querySelectorAll('input')){check('input',()=>{i.checked=true;i.value='12';i.dispatch('change');i.dispatch('input')})}

console.log('charts built',charts,'destroyed',destroyed);
console.log('clicked',clicked,'toasts',doc.getElementById('toasts').children.length,'errors',errs);
console.log(errs?'SMOKE FAILED':'smoke ok');
if(errs)process.exitCode=1;
