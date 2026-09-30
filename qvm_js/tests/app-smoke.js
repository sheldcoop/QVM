/**
 * tests/app-smoke.js - dev only, no dependencies:  node tests/app-smoke.js
 *
 * Boots the real shell in the fake browser, walks all six routes, clicks the
 * theme button. Exits 1 on any failure. Looks, layout and CSS are Prince's
 * job in Edge; this proves flows.
 */
const vm = require('vm'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const IDS = ['shell', 'brandMark', 'brandVer', 'themeBtn', 'helpBtn', 'alertBanner',
  'nav', 'navItems', 'navRev', 'navCollapse', 'main', 'toasts', 'dialogHost'];
const { win, doc, flush } = require('./fake-dom')({ ids: IDS, url: 'file:///x/index.html' });
const ctx = vm.createContext(win);
['js/config.js', 'js/themes.js', 'js/qvm-defaults.js', 'js/domain.js', 'js/parse.js',
 'js/settings.js', 'js/session.js',
 'js/ui/core.js', 'js/ui/components.js', 'js/ui/glyphs.js', 'js/ui/overlays.js',
 'js/ui/charts.js', 'js/ui/upload.js', 'js/qc.js',
 'js/views/panelmap.js', 'js/views/ptv.js', 'js/views/vtp.js', 'js/views/coreshk.js',
 'js/views/settings.js', 'js/views/health.js', 'js/views/help.js', 'js/app.js'
].forEach(f => vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f }));

// DOMContentLoaded never fires here; init directly like the listener would.
win.QVM.app.init();
flush();

let errs = 0;
function expect(name, cond) { if (!cond) { errs++; console.log('FAIL', name); } }

const main = doc.getElementById('main');
const routes = win.QVM.app.NAV;
expect('seven routes', routes.length === 7);

routes.forEach(function (r) {
  win.location.hash = r.hash;
  flush();
  const items = doc.getElementById('navItems').querySelectorAll('.nav-item');
  expect(r.label + ': nav has 7 items', items.length === 7);
  const active = items.filter(a => a.classList.contains('is-active'));
  expect(r.label + ': one active nav item', active.length === 1 && active[0].textContent === r.label);
  const h2 = main.querySelector('h2');
  expect(r.label + ': main shows the view', !!h2 && h2.textContent === r.label);
});

const before = doc.documentElement.getAttribute('data-theme');
// fake-dom builds bare divs; the real index.html carries data-action attributes.
doc.getElementById('themeBtn').dataset.action = 'cycle-theme';
doc.getElementById('themeBtn').click();
flush();
const after = doc.documentElement.getAttribute('data-theme');
expect('theme button cycles the theme', !!after && after !== before);

expect('shell visible', !doc.getElementById('shell').hidden);
expect('version stamped', doc.getElementById('brandVer').textContent === win.QVM.config.version);

console.log(errs ? 'APP-SMOKE FAILED' : 'app-smoke ok');
if (errs) process.exitCode = 1;
