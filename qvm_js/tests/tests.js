/**
 * tests/tests.js - every domain rule, with a test.
 *
 * Runs in tests/test.html (open it in Edge or Chrome) and from the command
 * line (node tests/run-tests.js). Results land in window.QVM_TESTS:
 *   {groups: [{name, rows: [{ok, name, detail}]}], passed, failed, done (Promise)}
 * UI components are covered by tests/ui-smoke.js (fake DOM), not here.
 */
(function () {
  'use strict';

  var D = window.QVM.domain;
  var cfg = window.QVM.config;
  var TH = window.QVM.themes;

  /* ---------------- tiny test runner ---------------- */
  var T = window.QVM_TESTS = { groups: [], passed: 0, failed: 0, done: null };
  var current = null;

  function group(name) { current = { name: name, rows: [] }; T.groups.push(current); }

  function record(ok, name, detail) {
    if (ok) T.passed++; else T.failed++;
    current.rows.push({ ok: ok, name: name, detail: detail || '' });
  }

  function eq(name, actual, expected) {
    var a = JSON.stringify(actual), e = JSON.stringify(expected);
    record(a === e, name, a === e ? '' : 'expected ' + e + ', got ' + a);
  }

  function ok(name, cond, detail) { record(!!cond, name, cond ? '' : (detail || 'expected true')); }

  function run() {
    /* =============== config =============== */
    group('Config');
    eq('app name', cfg.app_name, 'QVM Dashboard');
    ok('local prefix', typeof cfg.local_prefix === 'string' && cfg.local_prefix.length > 0);
    ok('config frozen', Object.isFrozen(cfg));

    /* =============== domain =============== */
    group('Domain shell');
    eq('schema version starts at 1', D.SCHEMA_VERSION, 1);

    /* =============== themes =============== */
    group('Themes');
    ok('theme list non-empty', TH.list.length > 0);
    ok('default theme exists', !!TH.byKey(TH.DEFAULT));
    ok('unknown key falls back to default', TH.byKey('no-such-theme') === null);
    ok('attrs carry scheme, never rely on name',
      TH.list.every(function (t) { var a = TH.attrs(t.key); return !!a['data-scheme']; }));
    ok('every theme has tokens', TH.list.every(function (t) {
      var v = TH.tokens(t); return v && v.bg && v.fg && v.surface;
    }));

    T.done = Promise.resolve();
  }

  run();
})();
