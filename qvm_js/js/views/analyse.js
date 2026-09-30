/**
 * QVM Dashboard - analyse view: the answer. Process pills auto-picked from
 * the job, verdict banner first, then scope, tiles, charts, table, panel-map
 * reference. No uploads here — files live on Upload.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.analyse = (function () {
  'use strict';

  function pills(main, ui, S, job) {
    var bar = ui.el('div', { class: 'qvm-pills' });
    job.processes.forEach(function (p) {
      var b = ui.el('button', { type: 'button',
        'class': 'qvm-pill' + (p.process === job.suggested ? ' is-now' : ''),
        'aria-pressed': p.process === job.suggested ? 'true' : 'false'
      }, [ui.el('span', { text: p.process }),
          ui.el('small', { text: p.rows + ' rows' })]);
      b.addEventListener('click', function () {
        S.setActiveProcess(p.process);
        window.QVM.app.refresh();
      });
      bar.appendChild(b);
    });
    main.appendChild(bar);
    return job.suggested;
  }

  function verdictBanner(main, ui, D, S) {
    var v = window.QVM.qc.jobVerdict();
    main.appendChild(ui.el('div', { class: 'qvm-verdict is-' + v.level,
      role: 'status' }, [
      ui.el('span', { 'class': 'v-word', text: v.level.toUpperCase() }),
      ui.el('ul', {}, v.reasons.map(function (r) { return ui.el('li', { text: r }); }))
    ]));
    return v;
  }

  function scopeBar(main, ui, S, rows, secondary) {
    var bar = ui.el('div', { class: 'qvm-row' });
    var panels = S.panels(rows);
    if (panels.length > 1) panels.unshift('All');
    var ui2 = ui;
    bar.appendChild(ui.segmented({ label: 'Panel', value: S.scope.panel,
      options: (panels.length ? panels : ['All']).map(function (p) { return { value: p, label: p }; }),
      onChange: function (x) { S.setScope({ panel: x }); window.QVM.app.refresh(); } }).node);
    var vals = S.columnValues(rows, secondary.col);
    if (vals.length > 1) vals.unshift('Both');
    bar.appendChild(ui.segmented({ label: secondary.label, value: S.scope[secondary.key],
      options: (vals.length ? vals : ['Both']).map(function (x) { return { value: x, label: x }; }),
      onChange: function (x) {
        var patch = {}; patch[secondary.key] = x;
        S.setScope(patch); window.QVM.app.refresh();
      } }).node);
    var bu = S.buStates(rows);
    if (bu.values.length + (bu.hasUnknown ? 1 : 0) > 1) {
      var opts = ['All'].concat(bu.values);
      if (bu.hasUnknown) opts.push('Unknown');
      bar.appendChild(ui.segmented({ label: 'Build Up', value: S.scope.buildUp,
        options: opts.map(function (x) { return { value: x, label: x }; }),
        onChange: function (x) { S.setScope({ buildUp: x }); window.QVM.app.refresh(); } }).node);
    } else if (bu.values.length === 1) {
      bar.appendChild(ui2.el('p', { text: 'Build Up: ' + bu.values[0] }));
    }
    main.appendChild(bar);
  }

  function scopedRows(S, rows, secondary) {
    return S.applyBu(
      S.applyScope(rows, { col: secondary.col, value: S.scope[secondary.key] }),
      S.scope.buildUp);
  }

  function qvmSection(main, ui, D, S, settings, process) {
    var names = settings.COLUMN_NAMES || {};
    var thresholdUm = parseFloat((settings.TOLERANCES || {}).annular_ring_min) || 0;
    var rows = S.rowsByProcess(process);
    scopeBar(main, ui, S, rows, { col: 'side', key: 'side', label: 'Side' });
    var scoped = scopedRows(S, rows, { col: 'side', key: 'side' });
    var q = window.QVM.qc;
    main.appendChild(ui.el('section', { class: 'panel' }, [ui.el('h2', { text: process })]));
    q.tiles(main, ui, D.annularStats(scoped, thresholdUm), thresholdUm);
    q.analyticsSection(main, ui, D, scoped, settings);
    q.measurementTable(main, ui, names, scoped, thresholdUm);
    q.shrinkageSection(main, ui, D, scoped, settings);
  }

  function csSection(main, ui, D, S, settings) {
    var nom = settings.NOMINAL_COORDS || {};
    var rows = S.rowsByProcess('Core Shrinkage');
    scopeBar(main, ui, S, rows, { col: 'layer', key: 'layer', label: 'Layer' });
    var scoped = S.applyScope(rows, { col: 'layer', value: S.scope.layer });
    var front = scoped.filter(function (r) { return r.layer === 'Front'; });
    var back = scoped.filter(function (r) { return r.layer === 'Back'; });
    var q = window.QVM.qc;
    [['Front', front], ['Back', back]].forEach(function (pair) {
      if (!pair[1].length) return;
      var s = D.affineSummary(D.analyzeLayer(pair[1], nom, settings));
      main.appendChild(ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: pair[0] + ' layer' }),
        s ? ui.el('div', { class: 'qvm-row' }, [
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
        ui.el('div', { class: 'qvm-row' }, [
          ui.kpiTile({ label: 'Pairs', value: String(fb.length) }).node,
          ui.kpiTile({ label: 'Mean Δ (µm)',
            value: dists.length ? D.mean(dists).toFixed(1) : '—' }).node,
          ui.kpiTile({ label: 'Max Δ (µm)',
            value: dists.length ? Math.max.apply(null, dists).toFixed(1) : '—' }).node
        ])
      ]));
    }
  }

  function mapReference(main, ui) {
    var details = ui.el('details', { class: 'panel' }, [
      ui.el('summary', { text: 'Panel map reference' })
    ]);
    details.appendChild(ui.el('img', { src: 'assets/Panel_Map.png',
      alt: 'Panel fiducial map: quarters UL, LL, LR, UR with grid IDs 11-44',
      style: { maxWidth: '100%', height: 'auto' } }));
    details.appendChild(ui.el('p', { text: 'Quarters run anticlockwise UL → LL → LR → UR.' }));
    main.appendChild(details);
  }

  function render(main) {
    var ui = window.QVM.ui, D = window.QVM.domain, S = window.QVM.session;
    var settings = window.QVM.settings.get();
    window.QVM.qc.stepper(main, 'analyse');
    var job = S.job();
    if (!job.processes.length) {
      main.appendChild(ui.emptyState({ icon: 'inbox', title: 'Nothing to analyse yet',
        text: 'Upload logs first — the app will know the process.',
        actionLabel: 'Go to Upload', onAction: function () { window.location.hash = '#/upload'; } }));
      return;
    }
    var active = pills(main, ui, S, job);
    verdictBanner(main, ui, D, S);
    if (active === 'Core Shrinkage') csSection(main, ui, D, S, settings);
    else qvmSection(main, ui, D, S, settings, active);
    window.QVM.qc.warningsSection(main, ui);
    mapReference(main, ui);
  }

  return { render: render };
})();
