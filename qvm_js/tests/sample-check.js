/**
 * tests/sample-check.js - dev only, no dependencies:  node tests/sample-check.js
 *
 * Parses the real sample-data files end to end (Node-only: browsers cannot
 * read the files). Exits 1 on any failure.
 */
const vm = require('vm'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const win = { console, Math, JSON };
win.window = win;
const ctx = vm.createContext(win);
['js/qvm-defaults.js', 'js/domain.js', 'js/parse.js'].forEach(f =>
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f }));
const P = win.QVM.parse, D = win.QVM.domain;

let errs = 0;
function expect(name, cond, detail) {
  if (!cond) { errs++; console.log('FAIL', name, detail || ''); }
}
function read(n) { return fs.readFileSync(path.join(ROOT, 'sample-data', n), 'utf8'); }

const ptv = P.ingestFile('Post PFC_Pad to Via_Panel 20_F.txt',
  read('Post PFC_Pad to Via_Panel 20_F.txt'), undefined, {});
expect('ptv 16 rows', ptv.rows.length === 16, ptv.rows.length);
expect('ptv process', ptv.rows[0].process === 'Pad to Via');
expect('ptv locations resolve',
  ptv.rows.every(r => /^[ULLR]{2}_\d$/.test(r.location)));
expect('ptv LR_3 fails', ptv.rows.some(r => r.location === 'LR_3' && r.sc * 1000 > 10));
expect('ptv quiet', ptv.parseWarnings.length + ptv.uiWarnings.length === 0);

const vtp = P.ingestFile('Post PFC_Via to Pad_Panel 20_F.txt',
  read('Post PFC_Via to Pad_Panel 20_F.txt'), undefined, {});
expect('vtp 4 rows', vtp.rows.length === 4, vtp.rows.length);
expect('vtp process', vtp.rows[0].process === 'Via to Pad');

const cs = P.ingestCsFile('C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt',
  read('C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt'), undefined, {});
expect('cs 16 dots', cs.rows.length === 16, cs.rows.length);
expect('cs quiet', cs.uiWarnings.length === 0, JSON.stringify(cs.uiWarnings));

const st = D.annularStats(ptv.rows, 0);
expect('ptv stats', st && st.n === 16);

console.log(errs ? 'SAMPLE-CHECK FAILED' : 'sample-check ok');
if (errs) process.exitCode = 1;
