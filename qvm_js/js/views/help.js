/**
 * QVM Dashboard - help view (M9)
 *
 * Analyst guide: file formats, scope, thresholds, export. Short and plain.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.help = (function () {
  'use strict';
  function render(main) {
    var ui = window.QVM.ui;
    main.appendChild(ui.el('h2', { text: 'Help' }));
    var sections = [
      ['Uploads', 'Drop one or more QVM .txt logs per tab. The filename can ' +
        'hint the type (VtP/PtV), panel (Panel 20), side (F/B), and build-up ' +
        '(BU-02); anything missing can be overridden per file. Core Shrinkage ' +
        'needs Front/Back in the filename or the layer override.'],
      ['Scope', 'Panel, Side/Layer, and Build Up narrow every table, tile, ' +
        'chart, and the shrinkage math below. Uploads stay in memory; only ' +
        'Settings survive a reload.'],
      ['Numbers', 'Annular ring = pad/2 − via/2 − SC. Tiles fail rows below ' +
        'the annular minimum (Settings). Zones follow the tolerance rings. ' +
        'Shrinkage is distance-only: no coordinate fit, no hidden transform.'],
      ['Charts', 'Bullseye, site bars, and box read SC in µm. The distortion ' +
        'map scales DX/DY arrows by sensitivity (default 100×) and colours ' +
        'them by pattern: Expansion, Contraction, Twist, Offset.'],
      ['Export', 'The workbook holds Report, process sheets, chart data, ' +
        'shrinkage summary, and warnings — all values in µm. Charts download ' +
        'as PNG separately; no Chrome needed.'],
      ['Samples', 'Built-in logs live in sample-data/ (regenerate with ' +
        'node sample-data/make-samples.js). The Core Shrinkage pair is the ' +
        'real CAM-order set from the Python app.']
    ];
    sections.forEach(function (s) {
      main.appendChild(ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: s[0] }),
        ui.el('p', { text: s[1] })
      ]));
    });
  }
  return { render: render };
})();
