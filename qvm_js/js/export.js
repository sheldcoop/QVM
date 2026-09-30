/**
 * QVM Dashboard - export.js (M9)
 *
 * SheetJS workbook builder + chart PNG downloads. Mirrors the Python sheets
 * (Report, process sheets, Analytics, Shrinkage Summary, Warnings) with one
 * deliberate exception (D12): SheetJS Community Edition cannot embed images,
 * so chart PNGs download separately via canvas.toDataURL — no Chrome needed.
 * All values in µm, rounded to 3 dp like the Python display frame.
 */
window.QVM = window.QVM || {};
window.QVM.export = (function () {
  'use strict';

  function r3(v) {
    if (v === null || v === undefined || isNaN(v)) return null;
    return Math.round(v * 1000 * 1000) / 1000;
  }

  function um(v) { return (v === null || v === undefined || isNaN(v)) ? null : r3(v * 1000); }

  function measurementRows(rows) {
    return (rows || []).map(function (r) {
      return { gridId: r.gridId, location: r.location || '',
        padUm: um(r.padDiameter), viaUm: um(r.viaDiameter),
        dxUm: um(r.dx), dyUm: um(r.dy), scUm: um(r.sc), annularUm: um(r.annularRing),
        buildUp: r.buildUp || '', panel: r.panel || '', side: r.side || '' };
    });
  }

  function processSheet(wb, title, rows, uslUm) {
    var head = ['Grid ID', 'Location', 'Pad Ø (µm)', 'Via Ø (µm)', 'DX (µm)', 'DY (µm)',
      'SC (µm)', 'Annular (µm)', 'USL (µm)', 'Build Up', 'Panel', 'Side'];
    var body = measurementRows(rows).map(function (m) {
      return [m.gridId, m.location, m.padUm, m.viaUm, m.dxUm, m.dyUm, m.scUm,
              m.annularUm, uslUm, m.buildUp, m.panel, m.side];
    });
    var ws = XLSX.utils.aoa_to_sheet([head].concat(body));
    ws['!cols'] = head.map(function () { return { wch: 14 }; });
    XLSX.utils.book_append_sheet(wb, ws, title);
  }

  function reportSheet(wb, vtpRows, ptvRows, settings, meta) {
    var head = ['Process', 'Grid ID', 'Location', 'SC (µm)', 'Annular (µm)',
      'USL (µm)', 'Build Up', 'Panel', 'Side', 'Source file'];
    var cfg = (settings && settings.VTP_REGISTRATION) || {};
    var cfg2 = (settings && settings.PTV_REGISTRATION) || {};
    function num(v, f) { var n = parseFloat(v); return isNaN(n) ? f : n; }
    var body = [];
    [['Via to Pad', vtpRows, num(cfg.vtp_usl_um, 10)],
     ['Pad to Via', ptvRows, num(cfg2.ptv_usl_um, 10)]].forEach(function (triple) {
      measurementRows(triple[1]).forEach(function (m) {
        body.push([triple[0], m.gridId, m.location, m.scUm, m.annularUm,
                   triple[2], m.buildUp, m.panel, m.side, meta.file || '']);
      });
    });
    if (!body.length) body.push(['No rows in scope.']);
    var ws = XLSX.utils.aoa_to_sheet([
      ['QVM Dashboard export', meta.date || ''],
      ['Source files', (meta.files || []).join('; ')]
    ].concat([[]]).concat([head]).concat(body));
    ws['!cols'] = [{ wch: 22 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 },
                   { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 24 }];
    XLSX.utils.book_append_sheet(wb, ws, 'Report');
  }

  function analyticsSheet(wb, title, rows, rings, D) {
    var head = ['Grid ID', 'Location', 'DX (µm)', 'DY (µm)', 'SC (µm)', 'Zone'];
    var body = measurementRows(rows).map(function (m) {
      return [m.gridId, m.location, m.dxUm, m.dyUm, m.scUm,
              m.scUm === null ? '' : D.zoneOf(m.scUm, rings)];
    });
    if (!body.length) body.push(['No rows in scope.']);
    var ws = XLSX.utils.aoa_to_sheet(
      [[title + ' — chart data (charts download as PNG separately)'], []]
      .concat([head]).concat(body));
    XLSX.utils.book_append_sheet(wb, ws, title.slice(0, 31));
  }

  function shrinkageSheet(wb, rows, settings, D) {
    var nom = (settings && settings.NOMINAL_COORDS) || {};
    var res = D.qpShrinkage(rows, nom, 50);
    var lines = [['Quadrant', 'X (ppm)', 'Y (ppm)']];
    res.quadrant.forEach(function (q) {
      lines.push([q.quadrant, Math.round(q.xPpm * 10) / 10, Math.round(q.yPpm * 10) / 10]);
    });
    lines.push([]);
    if (res.fullPanel)
      lines.push(['Full-panel X (ppm)', res.fullPanel.xPpm.toFixed(0)],
                 ['Full-panel Y (ppm)', res.fullPanel.yPpm.toFixed(0)],
                 ['QTQ X / Y (ppm)', res.uniformity.rangeX.toFixed(0) + ' / ' + res.uniformity.rangeY.toFixed(0)],
                 ['2D distortion (ppm)', res.uniformity.distortion2d.toFixed(0)]);
    lines.push([]);
    lines.push(['Outliers']);
    res.outliers.forEach(function (o) { lines.push([o.quadrant, o.alert]); });
    if (!res.outliers.length) lines.push(['None']);
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(lines), 'Shrinkage Summary');
  }

  function warningsSheet(wb, warnings) {
    var lines = [['File', 'Warning']];
    (warnings || []).forEach(function (w) { lines.push([w.file, w.text]); });
    if (lines.length === 1) lines.push(['', 'No warnings.']);
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(lines), 'Warnings');
  }

  /**
   * Build the full workbook. chartPngs unused by the sheets (D12) — kept in
   * the signature so a future xlsx-pro build can embed them without callers.
   */
  function buildQvmWorkbook(o) {
    var wb = XLSX.utils.book_new();
    processSheet(wb, 'Via to Pad', o.vtpRows, o.vtpUslUm);
    processSheet(wb, 'Pad to Via', o.ptvRows, o.ptvUslUm);
    reportSheet(wb, o.vtpRows, o.ptvRows, o.settings, o.meta || {});
    analyticsSheet(wb, 'Analytics VTP', o.vtpRows, o.rings, o.D);
    analyticsSheet(wb, 'Analytics PTV', o.ptvRows, o.rings, o.D);
    shrinkageSheet(wb, (o.vtpRows || []).concat(o.ptvRows || []), o.settings, o.D);
    warningsSheet(wb, o.warnings);
    return wb;
  }

  function downloadWorkbook(wb, filename) {
    XLSX.writeFile(wb, filename);
  }

  /** One-click PNG download of a live chart canvas (no Chrome needed). */
  function downloadPng(canvas, filename) {
    var a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  return {
    buildQvmWorkbook: buildQvmWorkbook,
    downloadWorkbook: downloadWorkbook,
    downloadPng: downloadPng
  };
})();
