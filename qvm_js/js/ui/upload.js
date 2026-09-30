/**
 * QVM Dashboard - ui/upload.js (M3)
 *
 * Multi-file upload panel with per-file overrides. Pure render from props;
 * the view owns file state and reads bytes via FileReader (M6 wires it).
 *   uploadPanel({ files, overrides, onPick, onOverride, onRemove })
 * files: [{name}], overrides: {name: {process, panel, side, buildUp}}.
 */
window.QVM = window.QVM || {};
window.QVM.ui = window.QVM.ui || {};
window.QVM.ui.uploadPanel = (function () {
  'use strict';

  function select(current, options, label) {
    var ui = window.QVM.ui;
    var s = ui.el('select', { 'aria-label': label });
    options.forEach(function (v) {
      var o = ui.el('option', { value: v, text: v === '' ? 'Auto' : v });
      if (v === current) o.setAttribute('selected', '');
      s.appendChild(o);
    });
    s.value = current;
    return s;
  }

  function uploadPanel(o) {
    var ui = window.QVM.ui;
    o = o || {};
    var files = o.files || [], overrides = o.overrides || {};
    var root = ui.el('div', { class: 'upload' });
    var input = ui.el('input', { type: 'file', accept: '.txt', multiple: true,
      'aria-label': 'QVM log files' });
    input.addEventListener('change', function () {
      if (typeof o.onPick === 'function') o.onPick(input.files || []);
    });
    root.appendChild(input);

    files.forEach(function (f) {
      var ov = overrides[f.name] || { process: '', panel: '', side: '', buildUp: '' };
      var row = ui.el('div', { class: 'upload-row' }, [
        ui.el('span', { class: 'upload-name', text: f.name })
      ]);
      var proc = select(ov.process, ['', 'Pad to Via', 'Via to Pad'], 'Type override for ' + f.name);
      proc.addEventListener('change', function () {
        if (typeof o.onOverride === 'function') o.onOverride(f.name, 'process', proc.value);
      });
      row.appendChild(proc);
      [['panel', 'Panel'], ['side', 'Side F/B'], ['buildUp', 'Build Up']].forEach(function (pair) {
        var inp = ui.el('input', { type: 'text', value: ov[pair[0]] || '',
          placeholder: pair[1], 'aria-label': pair[1] + ' override for ' + f.name });
        inp.addEventListener('change', function () {
          if (typeof o.onOverride === 'function') o.onOverride(f.name, pair[0], inp.value);
        });
        row.appendChild(inp);
      });
      var rm = ui.el('button', { type: 'button', text: 'Remove' });
      rm.addEventListener('click', function () {
        if (typeof o.onRemove === 'function') o.onRemove(f.name);
      });
      row.appendChild(rm);
      root.appendChild(row);
    });
    return root;
  }

  return uploadPanel;
})();
