/**
 * QVM Dashboard - export view: the final. Whole-job workbook, chart PNGs
 * from the Analyse charts, and the file manifest. Nothing to pick — the job
 * already knows everything.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.export = (function () {
  'use strict';

  function render(main) {
    var ui = window.QVM.ui, S = window.QVM.session;
    window.QVM.qc.stepper(main, 'export');
    var job = S.job();
    if (!job.processes.length) {
      main.appendChild(ui.emptyState({ icon: 'inbox', title: 'Nothing to export yet',
        text: 'Upload logs first, then come back.',
        actionLabel: 'Go to Upload', onAction: function () { window.location.hash = '#/upload'; } }));
      return;
    }

    main.appendChild(ui.el('h2', { text: 'Export' }));
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Workbook' }),
      ui.el('p', { text: 'Report, process sheets, chart data, shrinkage summary, ' +
        'and warnings — all values in µm, all processes in one file.' }),
      ui.el('div', { class: 'qvm-row' }, [
        ui.button('Download Excel', { kind: 'primary', onClick: function () {
          var job2 = window.QVM.qc.jobWorkbook();
          window.QVM.export.downloadWorkbook(job2.wb, job2.filename);
          ui.toast({ message: 'Workbook downloaded.', kind: 'success' });
        } })
      ])
    ]));

    var charts = window.QVM.qc.lastCharts || [];
    if (charts.length) {
      var row = ui.el('div', { class: 'qvm-row' });
      charts.forEach(function (h) {
        row.appendChild(ui.button(h.label + ' PNG', { onClick: function () {
          var ch = h.entry.chart();
          if (!ch) { ui.toast({ message: 'Chart not rendered yet.', kind: 'warning' }); return; }
          window.QVM.export.downloadPng(ch.canvas,
            'QVM_' + h.key + '_' + new Date().toISOString().slice(0, 10) + '.png');
        } }));
      });
      main.appendChild(ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: 'Chart PNGs' }),
        ui.el('p', { text: 'Captured from the Analyse charts — no Chrome needed.' }),
        row
      ]));
    } else {
      main.appendChild(ui.el('p', { text: 'Chart PNGs appear here after you visit Analyse.' }));
    }

    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Manifest' }),
      ui.el('ul', {}, S.files.map(function (f) {
        return ui.el('li', { text: f.name + ' — ' + f.rows.length + ' rows' });
      }))
    ]));
  }

  return { render: render };
})();
