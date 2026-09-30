/**
 * tests/run-tests.js - dev only, no dependencies:  node tests/run-tests.js
 *
 * Runs tests/tests.js (the same tests as tests/test.html) in Node, with the
 * real config, themes and domain. Prints every failure and a summary;
 * exits 1 on any failure.
 */
const vm = require('vm'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const win = { console, crypto: globalThis.crypto, TextEncoder, Intl, Date, Math, JSON, Promise,
              setTimeout, clearTimeout, Uint32Array, Uint8Array, Array, Object, String, Number, RegExp, Error };
win.window = win;
const ctx = vm.createContext(win);
['js/config.js', 'js/themes.js', 'js/qvm-defaults.js', 'js/domain.js', 'js/parse.js',
 'tests/tests.js'].forEach(f =>
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f }));

const T = win.QVM_TESTS;
T.done.then(() => {
  for (const g of T.groups) {
    const bad = g.rows.filter(r => !r.ok);
    console.log((bad.length ? 'FAIL ' : 'ok   ') + g.name + '  (' + (g.rows.length - bad.length) + '/' + g.rows.length + ')');
    for (const r of bad) console.log('       x ' + r.name + (r.detail ? '  -> ' + r.detail : ''));
  }
  console.log(T.failed ? T.failed + ' of ' + (T.passed + T.failed) + ' TESTS FAILED' : 'ALL ' + T.passed + ' TESTS PASSED');
  if (T.failed) process.exitCode = 1;
});
