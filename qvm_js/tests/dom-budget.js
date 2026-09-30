/**
 * tests/dom-budget.js - dev only, no dependencies:  node tests/dom-budget.js
 *
 * Boots the real shell in the fake browser, renders each view, logs render
 * ms + #main node counts, and fails when a view tops 5000 nodes. Fake-DOM
 * numbers measure JS render cost (no layout/paint); Prince checks real feel
 * in Edge. Budgets tighten as views fill in (M6-M8).
 */
const vm = require('vm'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const IDS = ['shell', 'brandMark', 'brandVer', 'themeBtn', 'helpBtn', 'alertBanner',
  'nav', 'navItems', 'navRev', 'navCollapse', 'main', 'toasts', 'dialogHost'];
const { win, doc, flush } = require('./fake-dom')({ ids: IDS, url: 'file:///x/index.html' });
const ctx = vm.createContext(win);
['js/config.js', 'js/themes.js', 'js/domain.js',
 'js/ui/core.js', 'js/ui/components.js', 'js/ui/glyphs.js', 'js/ui/overlays.js', 'js/ui/charts.js',
 'js/views/panelmap.js', 'js/views/ptv.js', 'js/views/vtp.js', 'js/views/coreshk.js',
 'js/views/health.js', 'js/views/help.js', 'js/app.js'
].forEach(f => vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f }));

win.QVM.app.init();
flush();

function nodes(el) { let n = 0; const w = x => x.children.forEach(c => { n++; w(c); }); w(el); return n; }

let fails = 0;
const main = doc.getElementById('main');
win.QVM.app.NAV.forEach(function (r) {
  win.location.hash = r.hash;
  flush();
  const t0 = performance.now(), n = nodes(main), ms = performance.now() - t0;
  console.log(r.label + ': ' + ms.toFixed(1) + ' ms, ' + n + ' nodes in #main');
  if (n > 5000) { fails++; console.log('FAIL ' + r.label + ': over the 5000-node view budget'); }
});
if (fails) process.exitCode = 1;
console.log(fails ? 'DOM BUDGET FAILED' : 'dom budget ok');
