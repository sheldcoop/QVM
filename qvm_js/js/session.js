/**
 * QVM Dashboard - session.js (M6)
 *
 * In-memory session state: uploaded files, their rows, per-file overrides,
 * and the shared scope selections. Views read; only views and the upload
 * flow write. Scope rules mirror the Python app: "All"/"Both" means no
 * filtering, and a frame missing the column passes through.
 */
window.QVM = window.QVM || {};
window.QVM.session = (function () {
  'use strict';

  var files = [];       // [{name, kind, rows, parseWarnings, uiWarnings}]
  var overrides = {};   // name -> {process, panel, side, buildUp, layer}
  var scope = { panel: 'All', side: 'Both', buildUp: 'All', layer: 'Both', vectorMult: 100 };

  function addFile(entry) {
    removeFile(entry.name);
    files.push(entry);
  }

  function removeFile(name) {
    files = files.filter(function (f) { return f.name !== name; });
  }

  function clear() { files = []; activeProcess = null; }

  function allRows() {
    var out = [];
    files.forEach(function (f) { out = out.concat(f.rows); });
    return out;
  }

  function rowsByProcess(process) {
    return allRows().filter(function (r) { return r.process === process; });
  }

  function warnings() {
    var out = [];
    files.forEach(function (f) {
      (f.parseWarnings || []).forEach(function (w) { out.push({ file: f.name, text: w }); });
      (f.uiWarnings || []).forEach(function (w) { out.push({ file: f.name, text: w }); });
    });
    return out;
  }

  function setScope(patch) {
    Object.keys(patch || {}).forEach(function (k) {
      if (scope[k] !== undefined) scope[k] = patch[k];
    });
  }

  /**
   * Panel + secondary scope filter. secondary: {col, value} e.g.
   * {col: 'side', value: 'F'} or {col: 'layer', value: 'Front'}.
   */
  function applyScope(rows, secondary) {
    var out = (rows || []).slice();
    if (scope.panel !== 'All')
      out = out.filter(function (r) { return !r.panel || r.panel === scope.panel; });
    if (secondary && secondary.value && secondary.value !== 'Both' &&
        ['side', 'layer'].indexOf(secondary.col) !== -1)
      out = out.filter(function (r) {
        return !r[secondary.col] || r[secondary.col] === secondary.value;
      });
    return out;
  }

  function panels(rows) {
    var seen = {};
    (rows || []).forEach(function (r) { if (r.panel) seen[r.panel] = true; });
    return Object.keys(seen).sort(naturalPanel);
  }

  function naturalPanel(a, b) {
    var da = /^\d+$/.test(a), db = /^\d+$/.test(b);
    if (da && db) return parseInt(a, 10) - parseInt(b, 10);
    if (da) return -1;
    if (db) return 1;
    return a < b ? -1 : 1;
  }

  function columnValues(rows, col) {
    var seen = {};
    (rows || []).forEach(function (r) {
      var v = r[col];
      if (v !== null && v !== undefined && String(v).trim() !== '') seen[String(v).trim()] = true;
    });
    return Object.keys(seen).sort();
  }

  /**
   * Build-Up selector states, mirroring the Python rules: a single known BU
   * is a label (no selector); Unknown alone filters to itself; otherwise a
   * selector with All + known values + Unknown last.
   */
  function buStates(rows) {
    var vals = columnValues(rows, 'buildUp').filter(function (v) { return v !== 'Unknown'; });
    var hasUnknown = columnValues(rows, 'buildUp').indexOf('Unknown') !== -1;
    return { values: vals, hasUnknown: hasUnknown };
  }

  function applyBu(rows, sel) {
    if (!sel || sel === 'All') return (rows || []).slice();
    if (sel === 'Unknown')
      return (rows || []).filter(function (r) { return r.buildUp === 'Unknown'; });
    return (rows || []).filter(function (r) { return r.buildUp === sel; });
  }

  var activeProcess = null;   // the Analyse pill selection; null = auto

  /**
   * Job summary: what the app knows after ingest. processes lists only
   * processes that actually have rows; suggested is the auto-pick for the
   * Analyse pills (QVM processes first, then Core Shrinkage).
   */
  function job() {
    var procs = [];
    ['Pad to Via', 'Via to Pad', 'Core Shrinkage'].forEach(function (p) {
      var n = rowsByProcess(p).length;
      if (n) procs.push({ process: p, rows: n });
    });
    var order = { 'Pad to Via': 0, 'Via to Pad': 1, 'Core Shrinkage': 2 };
    procs.sort(function (a, b) { return order[a.process] - order[b.process]; });
    var suggested = procs.length ? procs[0].process : null;
    if (activeProcess && procs.some(function (p) { return p.process === activeProcess; }))
      suggested = activeProcess;
    return { files: files.length, processes: procs, suggested: suggested,
             warnings: warnings().length };
  }

  function setActiveProcess(p) { activeProcess = p; }

  /**
   * Read a FileList via FileReader, auto-classify each file, and add it.
   * done() fires once all files settled (success or recorded failure).
   */
  function ingestFiles(fileList, done) {
    var settings = window.QVM.settings.get();
    var list = Array.prototype.slice.call(fileList || []);
    if (!list.length) { if (typeof done === 'function') done(); return; }
    var pending = list.length;
    function settle() { if (--pending === 0 && typeof done === 'function') done(); }
    list.forEach(function (f) {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var res = window.QVM.parse.classifyAndIngest(
            f.name, String(reader.result || ''), settings, overrides[f.name] || {});
          addFile({ name: f.name, kind: res.kind, rows: res.rows,
                    parseWarnings: res.parseWarnings, uiWarnings: res.uiWarnings });
        } catch (e) {
          addFile({ name: f.name, kind: 'qvm', rows: [],
                    parseWarnings: [], uiWarnings: ['`' + f.name + '`: ' + e.message] });
        }
        settle();
      };
      reader.onerror = function () {
        addFile({ name: f.name, kind: 'qvm', rows: [],
                  parseWarnings: [], uiWarnings: ['`' + f.name + '`: could not be read.'] });
        settle();
      };
      reader.readAsText(f);
    });
  }

  return {
    addFile: addFile,
    removeFile: removeFile,
    clear: clear,
    job: job,
    setActiveProcess: setActiveProcess,
    ingestFiles: ingestFiles,
    allRows: allRows,
    rowsByProcess: rowsByProcess,
    warnings: warnings,
    setScope: setScope,
    applyScope: applyScope,
    panels: panels,
    columnValues: columnValues,
    buStates: buStates,
    applyBu: applyBu,
    get files() { return files.slice(); },
    get overrides() { return overrides; },
    get scope() { return { panel: scope.panel, side: scope.side, buildUp: scope.buildUp,
      layer: scope.layer, vectorMult: scope.vectorMult }; }
  };
})();
