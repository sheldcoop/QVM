/**
 * tests/contrast.js - dev only, no dependencies:  node tests/contrast.js [all]
 *
 * WCAG AA (4.5:1) check of every text/background token pair in EVERY theme,
 * read straight from js/themes.js (the one place themes live), and that the
 * status colours stay clearly apart (CIEDE2000) in the new themes. Exits 1 on
 * any failure. (ui-kit.html shows the same table computed live in the browser.)
 */
const fs=require('fs'),path=require('path'),vm=require('vm');
const ctx={window:{}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'..','js/themes.js'),'utf8'),ctx);
const TH=ctx.window.QVM.themes;const T={};TH.list.forEach(t=>{T[t.key]=TH.tokens(t)});
function parse(c){let m;if(m=c.match(/^#([0-9a-f]{6})$/i)){const n=parseInt(m[1],16);return[n>>16,n>>8&255,n&255,1]}if(m=c.match(/rgba?\(([^)]+)\)/)){const p=m[1].split(',').map(Number);return[p[0],p[1],p[2],p[3]??1]}throw 'parse '+c}
const over=(a,b)=>[0,1,2].map(i=>a[i]*a[3]+b[i]*(1-a[3])).concat(1);
const L=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2])};
const ratio=(a,b)=>{const x=L(a),y=L(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
const pairs=[['fg','surface'],['fg-muted','surface'],['fg-muted','surface-2'],['fg-faint','surface'],['fg-faint','surface-2'],['fg-muted','bg'],['accent','surface'],['accent-fg','accent-fill'],['on-danger','danger'],['danger-fg','surface'],['danger-fg','danger-bg'],
...['ok','warning','critical','expired','blocked'].flatMap(s=>[[s+'-fg','surface'],[s+'-fg','surface-2'],[s+'-fg',s+'-bg']]),['c-blue','surface'],['c-teal','surface'],['c-pink','surface'],['fg','inset'],['accent','inset']];
let bad=0;const all=process.argv[2];
for(const[t,v]of Object.entries(T))for(const[f,b]of pairs){let bg=parse(v[b]);if(bg[3]<1)bg=over(bg,parse(v.surface));let fg=parse(v[f]);if(fg[3]<1)fg=over(fg,bg);const r=ratio(fg,bg);if(r<4.5)bad++;if(r<4.5||all)console.log(t.padEnd(8),(f+' on '+b).padEnd(30),r.toFixed(2),r>=4.5?'AA':'FAIL')}

// Status colours must stay clearly apart (Prince, 2026-09-25): Line stop / Late / Hot / Warning / OK.
// CIEDE2000 colour difference; fills (lamps, stripes, card edges - read at a glance) >= 15,
// text colours >= 12 (always shown with their word and icon). Checked for every theme.
// CIEDE2000 between two hex colours
function lab(hex){let [r,g,b]=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));
 let x=(r*.4124+g*.3576+b*.1805)/.95047,y=(r*.2126+g*.7152+b*.0722),z=(r*.0193+g*.1192+b*.9505)/1.08883;
 const f=t=>t>.008856?Math.cbrt(t):7.787*t+16/116;[x,y,z]=[f(x),f(y),f(z)];return[116*y-16,500*(x-y),200*(y-z)]}
function de2000(h1,h2){const[L1,a1,b1]=lab(h1),[L2,a2,b2]=lab(h2);const rad=Math.PI/180,deg=180/Math.PI;
 const C1=Math.hypot(a1,b1),C2=Math.hypot(a2,b2),Cm=(C1+C2)/2,G=.5*(1-Math.sqrt(Math.pow(Cm,7)/(Math.pow(Cm,7)+Math.pow(25,7))));
 const a1p=(1+G)*a1,a2p=(1+G)*a2,C1p=Math.hypot(a1p,b1),C2p=Math.hypot(a2p,b2);
 const h=(a,b)=>{if(!a&&!b)return 0;let v=Math.atan2(b,a)*deg;return v<0?v+360:v};const h1p=h(a1p,b1),h2p=h(a2p,b2);
 const dL=L2-L1,dC=C2p-C1p;let dh=0;if(C1p*C2p){dh=h2p-h1p;if(dh>180)dh-=360;else if(dh<-180)dh+=360}
 const dH=2*Math.sqrt(C1p*C2p)*Math.sin(dh*rad/2);const Lm=(L1+L2)/2,Cmp=(C1p+C2p)/2;
 let hm=h1p+h2p;if(C1p*C2p){if(Math.abs(h1p-h2p)>180)hm+=hm<360?360:-360;hm/=2}
 const T=1-.17*Math.cos((hm-30)*rad)+.24*Math.cos(2*hm*rad)+.32*Math.cos((3*hm+6)*rad)-.2*Math.cos((4*hm-63)*rad);
 const dTh=30*Math.exp(-Math.pow((hm-275)/25,2)),RC=2*Math.sqrt(Math.pow(Cmp,7)/(Math.pow(Cmp,7)+Math.pow(25,7)));
 const SL=1+.015*Math.pow(Lm-50,2)/Math.sqrt(20+Math.pow(Lm-50,2)),SC=1+.045*Cmp,SH=1+.015*Cmp*T,RT=-Math.sin(2*dTh*rad)*RC;
 return Math.sqrt(Math.pow(dL/SL,2)+Math.pow(dC/SC,2)+Math.pow(dH/SH,2)+RT*(dC/SC)*(dH/SH))}

const ST=['ok','warning','critical','expired'];
for(const t of TH.list){const v=T[t.key];for(let i=0;i<4;i++)for(let j=i+1;j<4;j++)for(const[k,min]of[['',15],['-fg',12]]){
  const d=de2000(v[ST[i]+k],v[ST[j]+k]);const low=d<min;if(low)bad++;
  if(low||all)console.log(t.key.padEnd(8),(ST[i]+k+' vs '+ST[j]+k).padEnd(30),'dE',d.toFixed(1),low?'TOO CLOSE':'distinct')}}
console.log('fails',bad);if(bad)process.exitCode=1;
