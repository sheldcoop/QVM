/**
 * tests/css-check.js - dev only, no dependencies:  node tests/css-check.js
 *
 * Guards css/app.css against the easy-to-miss breakages: unbalanced braces
 * (everything after them silently stops applying) and a component's rules
 * going missing in an edit. Exits 1 on failure. It also checks that no rule
 * keys on a theme's name: themes live in js/themes.js, the CSS keys on
 * data-scheme / data-contrast only.
 *
 * REQUIRED grows per milestone: add selectors when a new component lands.
 * (No print rules yet — print surfaces arrive with the export milestone.)
 */
const fs = require('fs'), path = require('path');
const css = fs.readFileSync(path.join(__dirname, '..', 'css/app.css'), 'utf8');

let depth = 0, line = 1, bad = 0;
for (const ch of css) {
  if (ch === '\n') line++;
  if (ch === '{') depth++;
  if (ch === '}' && --depth < 0) { console.log('unbalanced } at line', line); bad++; depth = 0; }
}
if (depth) { console.log('unclosed { at end of file'); bad++; }

// one or more key selectors per component; add yours when you add one
const REQUIRED = {
  tokens: [':root, [data-theme]', '[data-scheme="light"]', '[data-contrast="high"]'],   // the theme colours: js/themes.js
  panel: ['.panel-head', '.panel-title'],
  buttons: ['.btn-primary', '.btn-danger', '.btn-ghost'],
  segmented: ['.seg-opt input:checked + span'],
  field: ['.ifield-box'],
  kpi: ['.kpi-tile-value'], table: ['table.grid th'], tabs: ['.tab-ink'], dialog: ['dialog.modal'],
  toast: ['.toast-progress'], tooltip: ['.tip-card'], menu: ['.menu-item'],
  chart: ['.chart-box'], heatmap: ['.heat-cell::after'],
  glyph: ['.tool-glyph .tg-beam'],
  shell: ['.topbar', '.nav-item', '.alert-banner'],
  empty: ['.empty', '.skeleton'],
  motion: ['[data-motion="reduce"]', '.offscreen']
};
for (const [comp, sels] of Object.entries(REQUIRED)) {
  for (const s of sels) if (!css.includes(s)) { console.log('missing', comp + ':', s); bad++; }
}
const byName = css.split('\n').map((l, i) => [l, i + 1]).filter(x => /\[data-theme="/.test(x[0]) && !/^\s*(\/\*|\*)/.test(x[0]) && x[0].indexOf('live in ONE place') === -1);
byName.forEach(x => { console.log('line', x[1], 'keys on a theme name - use data-scheme / data-contrast, or put colours in js/themes.js'); bad++; });
console.log(bad ? bad + ' problem(s)' : 'css ok');
if (bad) process.exitCode = 1;
