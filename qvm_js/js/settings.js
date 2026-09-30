/**
 * QVM Dashboard - settings.js (M5)
 *
 * Analyst-tunable numbers (tolerance rings, USLs, outlier caps, CS
 * thresholds), persisted per PC in localStorage. Session uploads stay in
 * memory (D1); only these survive a reload. Deep-merges over
 * QVM.defaults.DEFAULT_SETTINGS so a partial stored blob can never break
 * a consumer. Memory fallback when storage is unavailable (private mode,
 * Node tests).
 */
window.QVM = window.QVM || {};
window.QVM.settings = (function () {
  'use strict';

  var KEY = 'qvm.settings.v1';
  var mem = null;

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function isObj(v) {
    return v !== null && typeof v === 'object' && !Array.isArray(v);
  }

  function deepMerge(base, patch) {
    var out = clone(base), k;
    if (!isObj(patch)) return out;
    for (k in patch) {
      if (isObj(patch[k]) && isObj(out[k])) out[k] = deepMerge(out[k], patch[k]);
      else out[k] = clone(patch[k]);
    }
    return out;
  }

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return mem; }
  }

  function write(obj) {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); }
    catch (e) { mem = clone(obj); }
  }

  function get() {
    return deepMerge(window.QVM.defaults.DEFAULT_SETTINGS, read() || {});
  }

  function set(patch) {
    var next = deepMerge(get(), patch || {});
    write(next);
    return next;
  }

  function reset() {
    var fresh = clone(window.QVM.defaults.DEFAULT_SETTINGS);
    write(fresh);
    return fresh;
  }

  return { KEY: KEY, get: get, set: set, reset: reset };
})();
