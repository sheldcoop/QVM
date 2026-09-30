/**
 * QVM Dashboard - settings view (M5)
 *
 * Analyst-editable tolerances and thresholds, persisted per PC. No PIN:
 * analyst-only tool. Forms read from QVM.settings; Save writes back.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.settings = (function () {
  'use strict';

  function numberSpecs(prefix, fields) {
    return fields.map(function (f) {
      return { key: prefix + '.' + f[0], label: f[1], kind: 'number', unit: f[2], hint: f[3] };
    });
  }

  function sectionValues(settings, prefix, keys) {
    var out = {}, src = settings[prefix] || {}, i;
    for (i = 0; i < keys.length; i++) out[prefix + '.' + keys[i]] = src[keys[i]];
    return out;
  }

  function sectionPatch(values, prefix, keys) {
    var patch = {}, sub = {}, i, v;
    for (i = 0; i < keys.length; i++) {
      v = values[prefix + '.' + keys[i]];
      if (typeof v === 'number' && !isNaN(v)) sub[keys[i]] = v;
    }
    patch[prefix] = sub;
    return patch;
  }

  function section(main, ui, title, prefix, fields, settings, forms) {
    var keys = fields.map(function (f) { return f[0]; });
    var form = ui.form(numberSpecs(prefix, fields), sectionValues(settings, prefix, keys));
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: title }), form.node
    ]));
    forms.push({ form: form, prefix: prefix, keys: keys });
  }

  function render(main) {
    var ui = window.QVM.ui, S = window.QVM.settings;
    var settings = S.get();
    main.appendChild(ui.el('h2', { text: 'Settings' }));
    main.appendChild(ui.el('p', { text: 'Tolerances and thresholds. Saved on this PC.' }));
    var forms = [];

    section(main, ui, 'Tolerance rings (µm)', 'VTP_REGISTRATION', [
      ['ring_exceptional_um', 'Exceptional', 'µm', 'Innermost bullseye ring'],
      ['ring_excellent_um', 'Excellent', 'µm', ''],
      ['ring_good_um', 'Good', 'µm', ''],
      ['ring_acceptable_um', 'Acceptable', 'µm', 'Beyond this is fail']
    ], settings, forms);

    section(main, ui, 'Spec limits', 'VTP_REGISTRATION', [
      ['vtp_usl_um', 'VtP USL', 'µm', 'Report sheet spec limit'],
      ['outlier_cap_um', 'Outlier cap', 'µm', 'SC above this is flagged']
    ], settings, forms);

    section(main, ui, 'Pad to Via', 'PTV_REGISTRATION', [
      ['ptv_usl_um', 'PtV USL', 'µm', ''],
      ['outlier_cap_um', 'Outlier cap', 'µm', '']
    ], settings, forms);

    section(main, ui, 'Quality gates', 'TOLERANCES', [
      ['annular_ring_min', 'Annular ring min', 'µm', 'Rows below this fail']
    ], settings, forms);

    section(main, ui, 'Core Shrinkage model', 'CORE_SHRINKAGE', [
      ['outlier_um', 'Outlier residual', 'µm', 'Dot above this is remeasured'],
      ['rotation_warn_deg', 'Rotation warn', '°', 'Fixturing, not shrinkage'],
      ['aniso_ppm', 'Anisotropy callout', 'ppm', ''],
      ['shrink_ppm', 'Real shrinkage floor', 'ppm', ''],
      ['shrink_usl_ppm', 'Headline spec', 'ppm', '']
    ], settings, forms);

    // The spec-limit section reuses VTP fields already saved above; merge, not overwrite.
    var bar = ui.el('div', { class: 'kit-row' }, [
      ui.button('Save', { kind: 'primary', onClick: function () {
        var patch = {};
        forms.forEach(function (entry) {
          var sub = sectionPatch(entry.form.values(), entry.prefix, entry.keys);
          Object.keys(sub[entry.prefix]).forEach(function (k) {
            patch[entry.prefix] = patch[entry.prefix] || {};
            patch[entry.prefix][k] = sub[entry.prefix][k];
          });
        });
        S.set(patch);
        ui.toast({ message: 'Settings saved on this PC.', kind: 'success' });
      } }),
      ui.button('Reset to defaults', { kind: 'ghost', onClick: function () {
        S.reset();
        renderFresh();
        ui.toast({ message: 'Settings reset to defaults.', kind: 'info' });
      } })
    ]);
    main.appendChild(bar);

    function renderFresh() {
      main.textContent = '';
      render(main);
    }
  }

  return { render: render };
})();
