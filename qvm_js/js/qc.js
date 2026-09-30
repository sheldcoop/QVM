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

  function seg(label, value, values, onChange) {
    var ui = window.QVM.ui;
    return ui.segmented({ label: label, value: value,
      options: values.map(function (v) { return { value: v, label: v }; }),
      onChange: onChange });
  }

  function readAndIngest(fileList, kind, done) {
    var S = window.QVM.session, st = window.QVM.settings.get();
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) { done(); return; }
    var pending = files.length;
    files.forEach(function (f) {
      var reader = new FileReader();
      reader.onload = function () {
        var text = String(reader.result || '');
        try {
          var res = kind === 'cs'
            ? window.QVM.parse.ingestCsFile(f.name, text, st, S.overrides[f.name] || {})
            : window.QVM.parse.ingestFile(f.name, text, st, S.overrides[f.name] || {});
          S.addFile({ name: f.name, kind: kind, rows: res.rows,
                      parseWarnings: res.parseWarnings, uiWarnings: res.uiWarnings });
        } catch (e) {
          S.addFile({ name: f.name, kind: kind, rows: [],
                      parseWarnings: [], uiWarnings: ['`' + f.name + '`: ' + e.message] });
        }
        if (--pending === 0) done();
      };
      reader.onerror = function () {
        S.addFile({ name: f.name, kind: kind, rows: [],
                    parseWarnings: [], uiWarnings: ['`' + f.name + '`: could not be read.'] });
        if (--pending === 0) done();
      };
      reader.readAsText(f);
    });
  }

  function uploadSection(main, ui, kind) {
    var S = window.QVM.session;
    var panel = ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Uploads' })
    ]);
    var box = ui.el('div');
    panel.appendChild(box);
    function draw() {
      box.textContent = '';
      box.appendChild(ui.uploadPanel({
        files: S.files.filter(function (f) { return f.kind === kind; })
                      .map(function (f) { return { name: f.name }; }),
        overrides: S.overrides,
        layerSelect: kind === 'cs',
        onPick: function (list) { readAndIngest(list, kind, window.QVM.app.refresh); },
        onOverride: function (name, key, value) {
          S.overrides[name] = S.overrides[name] || {};
          S.overrides[name][key] = value;
        },
        onRemove: function (name) { S.removeFile(name); window.QVM.app.refresh(); }
      }));
    }
    draw();
    main.appendChild(panel);
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
    main.appendChild(ui.el('div', { class: 'kit-row' }, [
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
      ui.el('div', { class: 'kit-row' }, [
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
    sec.appendChild(ui.el('div', { class: 'kit-row' }, [
      ui.el('span', { text: 'Distortion map sensitivity' }),
      seg('Sensitivity', String(mult), ['50', '100', '200', '400'], function (v) {
        window.QVM.session.setScope({ vectorMult: parseInt(v, 10) });
        window.QVM.app.refresh();
      })
    ]));
    addChart(C.quiverBuild(usable, settings, mult),
      { height: 520, label: 'ABF distortion map, ' + mult + 'x', expand: true, format: tip }, 'quiver');
    main.appendChild(sec);
  }

  function exportSection(main, ui, D, scoped, settings, process) {
    var E = window.QVM.export, S = window.QVM.session;
    var cfg = settings.VTP_REGISTRATION || {}, cfg2 = settings.PTV_REGISTRATION || {};
    function num(v, f) { var n = parseFloat(v); return isNaN(n) ? f : n; }
    var rings = D.getRings(settings);
    var files = S.files.filter(function (f) { return f.kind === 'qvm'; }).map(function (f) {
      return f.name;
    });
    var meta = { date: new Date().toISOString().slice(0, 10), files: files };
    var sec = ui.el('section', { class: 'panel' }, [ui.el('h2', { text: 'Export' })]);
    var row = ui.el('div', { class: 'kit-row' }, [
      ui.button('Download Excel', { kind: 'primary', onClick: function () {
        var wb = E.buildQvmWorkbook({
          vtpRows: S.rowsByProcess('Via to Pad'),
          ptvRows: S.rowsByProcess('Pad to Via'),
          vtpUslUm: num(cfg.vtp_usl_um, 10), ptvUslUm: num(cfg2.ptv_usl_um, 10),
          rings: rings, settings: settings, meta: meta,
          warnings: S.warnings(), D: D
        });
        E.downloadWorkbook(wb, 'QVM_' + process.replace(/ /g, '') + '_' + meta.date + '.xlsx');
        ui.toast({ message: 'Workbook downloaded.', kind: 'success' });
      } })
    ]);
    (window.QVM.qc.lastCharts || []).forEach(function (h) {
      row.appendChild(ui.button(h.label + ' PNG', { onClick: function () {
        var ch = h.entry.chart();
        if (!ch) { ui.toast({ message: 'Chart not rendered yet.', kind: 'warning' }); return; }
        E.downloadPng(ch.canvas, 'QVM_' + h.key + '_' + meta.date + '.png');
      } }));
    });
    sec.appendChild(row);
    sec.appendChild(ui.el('p', { text: 'Workbook holds Report, process sheets, chart data, ' +
      'shrinkage summary, and warnings. Charts download as PNG separately.' }));
    main.appendChild(sec);
  }

  /* ---------------- public views ---------------- */

  function renderQcView(main, process) {
    var ui = window.QVM.ui, D = window.QVM.domain, S = window.QVM.session;
    var settings = window.QVM.settings.get();
    var names = (settings.COLUMN_NAMES) || {};
    var thresholdUm = parseFloat((settings.TOLERANCES || {}).annular_ring_min) || 0;

    main.appendChild(ui.el('h2', { text: process }));
    uploadSection(main, ui, 'qvm');

    var rows = S.rowsByProcess(process);
    if (!rows.length) {
      main.appendChild(ui.emptyState({ icon: 'inbox', title: 'No ' + process + ' data',
        text: 'Upload one or more .txt logs above.' }));
      warningsSection(main, ui);
      return;
    }

    // Scope bar: Panel + Side + Build Up.
    var bar = ui.el('div', { class: 'kit-row' });
    var panels = S.panels(rows);
    if (panels.length > 1) panels.unshift('All');
    bar.appendChild(seg('Panel', S.scope.panel, panels.length ? panels : ['All'],
      function (v) { S.setScope({ panel: v }); window.QVM.app.refresh(); }));
    var sides = S.columnValues(rows, 'side');
    if (sides.length > 1) sides.unshift('Both');
    bar.appendChild(seg('Side', S.scope.side, sides.length ? sides : ['Both'],
      function (v) { S.setScope({ side: v }); window.QVM.app.refresh(); }));
    var bu = S.buStates(rows);
    if (bu.values.length + (bu.hasUnknown ? 1 : 0) > 1) {
      var opts = ['All'].concat(bu.values);
      if (bu.hasUnknown) opts.push('Unknown');
      bar.appendChild(seg('Build Up', S.scope.buildUp, opts,
        function (v) { S.setScope({ buildUp: v }); window.QVM.app.refresh(); }));
    } else if (bu.values.length === 1) {
      bar.appendChild(ui.el('p', { text: 'Build Up: ' + bu.values[0] }));
    }
    main.appendChild(bar);

    var scoped = S.applyBu(
      S.applyScope(rows, { col: 'side', value: S.scope.side }), S.scope.buildUp);

    main.appendChild(ui.el('section', { class: 'panel' }, [ui.el('h2', { text: 'Quality' })]));
    tiles(main, ui, D.annularStats(scoped, thresholdUm), thresholdUm);
    analyticsSection(main, ui, D, scoped, settings);
    measurementTable(main, ui, names, scoped, thresholdUm);
    shrinkageSection(main, ui, D, scoped, settings);
    exportSection(main, ui, D, scoped, settings, process);
    warningsSection(main, ui);
  }

  function renderCsView(main) {
    var ui = window.QVM.ui, D = window.QVM.domain, S = window.QVM.session;
    var settings = window.QVM.settings.get();
    var nom = settings.NOMINAL_COORDS || {};

    main.appendChild(ui.el('h2', { text: 'Core Shrinkage' }));
    uploadSection(main, ui, 'cs');

    var rows = S.rowsByProcess('Core Shrinkage');
    if (!rows.length) {
      main.appendChild(ui.emptyState({ icon: 'inbox', title: 'No Core Shrinkage data',
        text: 'Upload front/back .txt logs above.' }));
      warningsSection(main, ui);
      return;
    }

    var bar = ui.el('div', { class: 'kit-row' });
    var panels = S.panels(rows);
    if (panels.length > 1) panels.unshift('All');
    bar.appendChild(seg('Panel', S.scope.panel, panels.length ? panels : ['All'],
      function (v) { S.setScope({ panel: v }); window.QVM.app.refresh(); }));
    bar.appendChild(seg('Layer', S.scope.layer, ['Both', 'Front', 'Back'],
      function (v) { S.setScope({ layer: v }); window.QVM.app.refresh(); }));
    main.appendChild(bar);

    var scoped = S.applyScope(rows, { col: 'layer', value: S.scope.layer });
    var front = scoped.filter(function (r) { return r.layer === 'Front'; });
    var back = scoped.filter(function (r) { return r.layer === 'Back'; });

    [['Front', front], ['Back', back]].forEach(function (pair) {
      if (!pair[1].length) return;
      var a = D.analyzeLayer(pair[1], nom, settings);
      var s = D.affineSummary(a);
      main.appendChild(ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: pair[0] + ' layer' }),
        s ? ui.el('div', { class: 'kit-row' }, [
          ui.kpiTile({ label: 'Pattern', value: s.pattern,
            status: s.pattern === 'Stable' ? 'ok' : 'warning' }).node,
          ui.kpiTile({ label: 'X / Y (ppm)',
            value: s.sxPpm.toFixed(0) + ' / ' + s.syPpm.toFixed(0) }).node,
          ui.kpiTile({ label: 'RMS / max (µm)',
            value: s.rmsUm.toFixed(1) + ' / ' + s.maxUm.toFixed(1) }).node,
          ui.kpiTile({ label: 'Outliers', value: String(s.nOutliers),
            status: s.nOutliers ? 'warning' : 'ok',
            sub: s.outliers.join(', ') }).node
        ]) : ui.el('p', { text: 'Fewer than 4 fiducials match nominal.' })
      ]));
    });

    if (front.length && back.length) {
      var fb = D.frontBack(front, back);
      var dists = fb.map(function (r) { return r.distUm; });
      main.appendChild(ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: 'Front ↔ Back registration' }),
        ui.el('div', { class: 'kit-row' }, [
          ui.kpiTile({ label: 'Pairs', value: String(fb.length) }).node,
          ui.kpiTile({ label: 'Mean Δ (µm)',
            value: dists.length ? D.mean(dists).toFixed(1) : '—' }).node,
          ui.kpiTile({ label: 'Max Δ (µm)',
            value: dists.length ? Math.max.apply(null, dists).toFixed(1) : '—' }).node
        ]),
        ui.el('div', { class: 'table-wrap' }, ui.el('table', { class: 'grid' }, [
          ui.el('tr', {}, ['Location', 'ΔX (µm)', 'ΔY (µm)', 'Δ (µm)'].map(function (h) {
            return ui.el('th', { text: h });
          }))
        ].concat(fb.map(function (r) {
          return ui.el('tr', {}, [r.location, r.dxUm.toFixed(1), r.dyUm.toFixed(1),
            r.distUm.toFixed(1)].map(function (v) {
            return ui.el('td', { text: String(v) });
          }));
        }))))
      ]));
    }
    warningsSection(main, ui);
  }

  return { renderQcView: renderQcView, renderCsView: renderCsView };
})();
