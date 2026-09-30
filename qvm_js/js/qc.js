/**
 * QVM Dashboard - qc.js (M6)
 *
 * Shared Quality-Control renderers for the PtV/VtP views (measurement table,
 * stat tiles, scope bar, upload wiring) and the Core Shrinkage view
 * (per-layer summaries, front-back table). Views delegate; session owns data.
 */
window.QVM = window.QVM || {};
window.QVM.qc = (function () {
  'use strict';

  function fmt(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return (v * 1000).toFixed(digits === undefined ? 3 : digits);
  }

  function sortedByGrid(rows) {
    return (rows || []).slice().sort(function (a, b) {
      if (a.gridId === null || a.gridId === undefined) return 1;
      if (b.gridId === null || b.gridId === undefined) return -1;
      return a.gridId - b.gridId;
    });
  }

  /** Flow stepper: Upload → Analyse → Export with done states from the job. */
  function stepper(main, now) {
    var ui = window.QVM.ui, job = window.QVM.session.job();
    var steps = [
      { key: 'upload', label: 'Upload', hash: '#/upload',
        done: job.files > 0 },
      { key: 'analyse', label: 'Analyse', hash: '#/analyse',
        done: job.processes.length > 0 },
      { key: 'export', label: 'Export', hash: '#/export', done: false }
    ];
    main.appendChild(ui.el('div', { class: 'qvm-steps' }, steps.map(function (s, i) {
      var cls = 'qvm-step' + (s.key === now ? ' is-now' : '') + (s.done ? ' is-done' : '');
      return ui.el('a', { href: s.hash, 'class': cls }, [
        ui.el('span', { 'class': 'n', text: String(i + 1) }),
        ui.el('span', { text: s.label })
      ]);
    })));
  }

  function warningsSection(main, ui) {
    var list = window.QVM.session.warnings();
    if (!list.length) return;
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Warnings (' + list.length + ')' }),
      ui.el('ul', {}, list.map(function (w) {
        return ui.el('li', { text: w.file + ': ' + w.text });
      }))
    ]));
  }

  function tiles(main, ui, stats, thresholdUm) {
    if (!stats) {
      main.appendChild(ui.el('p', { text: 'No measurable rows in scope.' }));
      return;
    }
    var failStatus = stats.failCount > 0 ? 'critical' : 'ok';
    main.appendChild(ui.el('div', { class: 'qvm-row' }, [
      ui.kpiTile({ label: 'Sites', value: String(stats.n) }).node,
      ui.kpiTile({ label: 'Min ring (µm)', value: stats.min.toFixed(3) }).node,
      ui.kpiTile({ label: 'Max ring (µm)', value: stats.max.toFixed(3) }).node,
      ui.kpiTile({ label: 'Mean ± std (µm)',
        value: stats.mean.toFixed(3) + ' ± ' + (isNaN(stats.std) ? '—' : stats.std.toFixed(3)) }).node,
      ui.kpiTile({ label: 'Worst site',
        value: stats.worst.location + ' (' + stats.worst.valueUm.toFixed(1) + ' µm)' }).node,
      ui.kpiTile({ label: 'Fails < ' + thresholdUm + ' µm', value: String(stats.failCount),
        status: failStatus, sub: stats.failPct.toFixed(1) + '% of sites' }).node
    ]));
  }

  function measurementTable(main, ui, names, rows, thresholdUm) {
    var head = ['Grid ID', 'Location', names.outer_diameter + ' (µm)',
      names.inner_diameter + ' (µm)', names.x_distance + ' (µm)',
      names.y_distance + ' (µm)', names.ptv_distance + ' (µm)',
      names.annular_ring + ' (µm)'];
    var table = ui.el('table', { class: 'grid' }, [
      ui.el('tr', {}, head.map(function (h) { return ui.el('th', { text: h }); }))
    ]);
    sortedByGrid(rows).forEach(function (r) {
      var fail = r.annularRing !== null && r.annularRing !== undefined &&
                 r.annularRing * 1000 < thresholdUm;
      var cells = [
        ui.el('td', { text: r.gridId === null || r.gridId === undefined ? '—' : String(r.gridId) }),
        ui.el('td', { text: r.location || '—' }),
        ui.el('td', { text: fmt(r.padDiameter) }),
        ui.el('td', { text: fmt(r.viaDiameter) }),
        ui.el('td', { text: fmt(r.dx) }),
        ui.el('td', { text: fmt(r.dy) }),
        ui.el('td', { text: fmt(r.sc) })
      ];
      var ringCell = ui.el('td', {}, fail ? [ui.led('critical'), ui.el('span', { text: ' ' + fmt(r.annularRing) })]
                                          : [ui.el('span', { text: fmt(r.annularRing) })]);
      cells.push(ringCell);
      table.appendChild(ui.el('tr', {}, cells));
    });
    main.appendChild(ui.el('div', { class: 'table-wrap' }, table));
  }

  function shrinkageSection(main, ui, D, rows, settings) {
    var nom = (settings && settings.NOMINAL_COORDS) || {};
    var res = D.qpShrinkage(rows, nom, 50);
    if (!res.quadrant.length) return;
    var fp = res.fullPanel, uni = res.uniformity;
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Distance shrinkage' }),
      ui.el('div', { class: 'qvm-row' }, [
        ui.kpiTile({ label: 'FP X / Y (ppm)',
          value: fp.xPpm.toFixed(0) + ' / ' + fp.yPpm.toFixed(0) }).node,
        ui.kpiTile({ label: 'QTQ X / Y (ppm)',
          value: uni.rangeX.toFixed(0) + ' / ' + uni.rangeY.toFixed(0) }).node,
        ui.kpiTile({ label: '2D distortion (ppm)', value: uni.distortion2d.toFixed(0) }).node,
        ui.kpiTile({ label: 'Outliers', value: String(res.outliers.length),
          status: res.outliers.length ? 'warning' : 'ok',
          sub: res.outliers.map(function (o) { return o.quadrant; }).join(', ') }).node
      ])
    ]));
  }

  function analyticsSection(main, ui, D, rows, settings) {
    var C = window.QVM.charts;
    var rings = D.getRings(settings);
    var usable = rows.filter(function (r) {
      return r.dx !== null && r.dx !== undefined && r.sc !== null && r.sc !== undefined;
    });
    if (!usable.length) return;
    function tip(raw) { return (raw && raw.tip) || ''; }
    var mult = window.QVM.session.scope.vectorMult || 100;
    var sec = ui.el('section', { class: 'panel' }, [ui.el('h2', { text: 'Analytics' })]);
    var handles = [];
    window.QVM.qc.lastCharts = handles;
    function addChart(build, opts, key) {
      var entry = ui.chart(build, opts);
      handles.push({ key: key, label: opts.label, entry: entry });
      sec.appendChild(entry.node);
    }
    addChart(C.bullseyeBuild(usable, rings),
      { height: 420, label: 'Registration bullseye', expand: true, format: tip }, 'bullseye');
    addChart(C.siteBarsBuild(usable, rings),
      { height: 300, label: 'Per-site SC', expand: true, format: tip }, 'sitebars');
    var quarters = usable.filter(function (r) { return (r.location || '').indexOf('_') !== -1; });
    if (quarters.length)
      addChart(C.boxBuild(quarters),
        { height: 300, label: 'SC distribution by quarter', expand: true, format: tip }, 'box');
    sec.appendChild(ui.el('div', { class: 'qvm-row' }, [
      ui.el('span', { text: 'Distortion map sensitivity' }),
      ui.segmented({ label: 'Sensitivity', value: String(mult),
        options: ['50', '100', '200', '400'].map(function (x) { return { value: x, label: x + '×' }; }),
        onChange: function (v) {
          window.QVM.session.setScope({ vectorMult: parseInt(v, 10) });
          window.QVM.app.refresh();
        } }).node
    ]));
    addChart(C.quiverBuild(usable, settings, mult),
      { height: 520, label: 'ABF distortion map, ' + mult + 'x', expand: true, format: tip }, 'quiver');
    main.appendChild(sec);
  }

  /**
   * Whole-job verdict input: QC stats per QVM process, shrinkage outliers,
   * CS layer summaries, session warnings. The Analyse banner + Export gate.
   */
  function jobVerdict() {
    var D = window.QVM.domain, S = window.QVM.session;
    var settings = window.QVM.settings.get();
    var thresholdUm = parseFloat((settings.TOLERANCES || {}).annular_ring_min) || 0;
    var nom = settings.NOMINAL_COORDS || {};
    var qc = [], shrinkage = [], cs = [];
    ['Pad to Via', 'Via to Pad'].forEach(function (p) {
      var rows = S.rowsByProcess(p);
      if (!rows.length) return;
      qc.push({ process: p, thresholdUm: thresholdUm, stats: D.annularStats(rows, thresholdUm) });
      var shr = D.qpShrinkage(rows, nom, 50);
      if (shr.outliers.length)
        shrinkage.push({ label: p === 'Pad to Via' ? 'PTV' : 'VTP', limitPpm: 50, outliers: shr.outliers });
    });
    ['Front', 'Back'].forEach(function (layer) {
      var rows = S.rowsByProcess('Core Shrinkage').filter(function (r) { return r.layer === layer; });
      if (!rows.length) return;
      var s = D.affineSummary(D.analyzeLayer(rows, nom, settings));
      if (s) cs.push({ layer: layer, nOutliers: s.nOutliers, outliers: s.outliers, pattern: s.pattern });
    });
    return D.verdict({ qc: qc, shrinkage: shrinkage, cs: cs, warnings: S.warnings() });
  }

  /** Full-job workbook for the Export view. */
  function jobWorkbook() {
    var D = window.QVM.domain, S = window.QVM.session, E = window.QVM.export;
    var settings = window.QVM.settings.get();
    function num(v, f) { var n = parseFloat(v); return isNaN(n) ? f : n; }
    var cfg = settings.VTP_REGISTRATION || {}, cfg2 = settings.PTV_REGISTRATION || {};
    var date = new Date().toISOString().slice(0, 10);
    var wb = E.buildQvmWorkbook({
      vtpRows: S.rowsByProcess('Via to Pad'),
      ptvRows: S.rowsByProcess('Pad to Via'),
      vtpUslUm: num(cfg.vtp_usl_um, 10), ptvUslUm: num(cfg2.ptv_usl_um, 10),
      rings: D.getRings(settings), settings: settings,
      meta: { date: date, files: S.files.map(function (f) { return f.name; }) },
      warnings: S.warnings(), D: D
    });
    return { wb: wb, filename: 'QVM_Job_' + date + '.xlsx' };
  }

  return { jobVerdict: jobVerdict, jobWorkbook: jobWorkbook,
           stepper: stepper, warningsSection: warningsSection,
           tiles: tiles, measurementTable: measurementTable,
           analyticsSection: analyticsSection, shrinkageSection: shrinkageSection,
           sortedByGrid: sortedByGrid };
})();
