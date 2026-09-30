/**
 * QVM Dashboard - upload view: the landing. Drop files, the app classifies
 * them; one-click samples; job summary with a CTA into Analyse.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.upload = (function () {
  'use strict';

  var SAMPLES = [
    { label: 'PtV sample · 16 sites', files: ['Post PFC_Pad to Via_Panel 20_F.txt'] },
    { label: 'VtP sample · 4 sites', files: ['Post PFC_Via to Pad_Panel 20_F.txt'] },
    { label: 'Core Shrinkage pair', files: [
      'C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt',
      'C4F_Core_Shrinkage_Panel 28_Back_CAMorder.txt'] }
  ];

  function loadSamples(names) {
    var S = window.QVM.session, ui = window.QVM.ui;
    var settings = window.QVM.settings.get();
    var pending = names.length, failed = 0;
    names.forEach(function (n) {
      fetch('sample-data/' + n).then(function (res) {
        if (!res.ok) throw new Error('missing');
        return res.text();
      }).then(function (text) {
        var r = window.QVM.parse.classifyAndIngest(n, text, settings, {});
        S.addFile({ name: n, kind: r.kind, rows: r.rows,
                    parseWarnings: r.parseWarnings, uiWarnings: r.uiWarnings });
      }).catch(function () { failed++; }).then(function () {
        if (--pending === 0) {
          if (failed) ui.toast({ message: 'Samples are blocked here — use the picker and choose the sample-data files.', kind: 'warning' });
          window.QVM.app.refresh();
        }
      });
    });
  }

  function render(main) {
    var ui = window.QVM.ui, S = window.QVM.session;
    window.QVM.qc.stepper(main, 'upload');

    main.appendChild(ui.el('div', { class: 'qvm-hero' }, [
      ui.el('h2', { text: 'Drop your QVM logs' }),
      ui.el('p', { text: 'Pad to Via, Via to Pad, Core Shrinkage — the app reads the ' +
        'content and knows which is which. No tabs to pick.' })
    ]));

    var input = ui.el('input', { type: 'file', accept: '.txt', multiple: true,
      'aria-label': 'QVM log files' });
    var drop = ui.el('div', { class: 'qvm-drop', tabindex: '0', role: 'button',
      'aria-label': 'Drop log files here or activate to browse' }, [
      ui.el('strong', { text: 'Drop .txt logs here, or click to browse' }),
      ui.el('span', { text: 'Multiple files welcome — panels, sides, and build-ups mix freely.' })
    ]);
    drop.appendChild(input);
    drop.addEventListener('click', function (e) {
      if (e.target !== input) input.click();
    });
    drop.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    ['dragenter', 'dragover'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('is-over'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('is-over'); });
    });
    drop.addEventListener('drop', function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length)
        S.ingestFiles(e.dataTransfer.files, window.QVM.app.refresh);
    });
    input.addEventListener('change', function () {
      S.ingestFiles(input.files || [], window.QVM.app.refresh);
      input.value = '';
    });
    main.appendChild(drop);

    var sampleRow = ui.el('div', { class: 'qvm-row' }, [
      ui.el('span', { text: 'No files handy? Try:' })
    ]);
    SAMPLES.forEach(function (s) {
      sampleRow.appendChild(ui.el('button', { type: 'button', 'class': 'btn-ghost',
        onclick: function () { loadSamples(s.files); } }, s.label));
    });
    main.appendChild(sampleRow);

    var job = S.job();
    if (job.files) {
      var card = ui.el('section', { class: 'panel' }, [
        ui.el('h2', { text: 'Job: ' + job.files + ' file' + (job.files === 1 ? '' : 's') })
      ]);
      card.appendChild(ui.el('ul', {}, job.processes.map(function (p) {
        return ui.el('li', { text: p.process + ' — ' + p.rows + ' rows' });
      })));
      if (job.warnings)
        card.appendChild(ui.el('p', { text: job.warnings + ' file warning' +
          (job.warnings === 1 ? '' : 's') + ' — see Analyse.' }));
      var go = ui.el('div', { class: 'qvm-row' }, [
        ui.button('Analyse →', { kind: 'primary', onClick: function () {
          window.location.hash = '#/analyse';
        } })
      ]);
      card.appendChild(go);
      main.appendChild(card);

      // Per-file overrides + removal live here; Analyse stays about the data.
      var box = ui.el('div');
      box.appendChild(ui.uploadPanel({
        files: S.files.map(function (f) { return { name: f.name }; }),
        overrides: S.overrides,
        layerSelect: true,
        onPick: function (list) { S.ingestFiles(list, window.QVM.app.refresh); },
        onOverride: function (name, key, value) {
          S.overrides[name] = S.overrides[name] || {};
          S.overrides[name][key] = value;
          ui.toast({ message: 'Override saved — re-drop the file to apply it.', kind: 'info' });
        },
        onRemove: function (name) { S.removeFile(name); window.QVM.app.refresh(); }
      }));
      main.appendChild(box);
    }
  }

  return { render: render };
})();
