/**
 * QVM Dashboard - health view (M10)
 *
 * Session data summary + environment checks on one screen.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.health = (function () {
  'use strict';

  function checkRow(ui, label, ok, detail) {
    return ui.el('tr', {}, [
      ui.el('td', { text: label }),
      ui.el('td', {}, [ui.led(ok ? 'ok' : 'critical')]),
      ui.el('td', { text: detail })
    ]);
  }

  function envChecks() {
    var out = [];
    out.push({ label: 'Chart.js vendor', ok: typeof window.Chart === 'function',
      detail: typeof window.Chart === 'function' ? 'present' : 'missing — charts show a notice' });
    out.push({ label: 'SheetJS vendor', ok: !!(window.XLSX && window.XLSX.utils),
      detail: window.XLSX && window.XLSX.utils ? 'present' : 'missing — export disabled' });
    var storageOk = false, storageDetail = '';
    try {
      localStorage.setItem('qvm.probe', '1');
      storageOk = localStorage.getItem('qvm.probe') === '1';
      localStorage.removeItem('qvm.probe');
      storageDetail = storageOk ? 'writable' : 'blocked — settings will not persist';
    } catch (e) { storageDetail = 'blocked — settings will not persist'; }
    out.push({ label: 'Settings storage', ok: storageOk, detail: storageDetail });
    var fromFile = String(window.location.protocol || '') === 'file:';
    out.push({ label: 'Launch', ok: true,
      detail: fromFile ? 'file:// — supported' : window.location.protocol + ' — also fine' });
    return out;
  }

  function render(main) {
    var ui = window.QVM.ui, S = window.QVM.session;
    var st = window.QVM.settings.get();
    main.appendChild(ui.el('h2', { text: 'Health' }));

    var files = S.files, rows = S.allRows();
    function count(process) {
      return rows.filter(function (r) { return r.process === process; }).length;
    }
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Session data' }),
      ui.el('div', { class: 'qvm-row' }, [
        ui.kpiTile({ label: 'Files', value: String(files.length) }).node,
        ui.kpiTile({ label: 'Pad to Via rows', value: String(count('Pad to Via')) }).node,
        ui.kpiTile({ label: 'Via to Pad rows', value: String(count('Via to Pad')) }).node,
        ui.kpiTile({ label: 'Core Shrinkage dots', value: String(count('Core Shrinkage')) }).node,
        ui.kpiTile({ label: 'Warnings', value: String(S.warnings().length),
          status: S.warnings().length ? 'warning' : 'ok' }).node
      ]),
      ui.el('p', { text: 'Annular minimum ' +
        st.TOLERANCES.annular_ring_min + ' µm · rings ' +
        [st.VTP_REGISTRATION.ring_exceptional_um, st.VTP_REGISTRATION.ring_excellent_um,
         st.VTP_REGISTRATION.ring_good_um, st.VTP_REGISTRATION.ring_acceptable_um].join('/') +
        ' µm · CS outlier ' + st.CORE_SHRINKAGE.outlier_um + ' µm' })
    ]));

    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Environment' }),
      ui.el('div', { class: 'table-wrap' }, ui.el('table', { class: 'grid' }, [
        ui.el('tr', {}, ['Check', 'Status', 'Detail'].map(function (h) {
          return ui.el('th', { text: h });
        }))
      ].concat(envChecks().map(function (c) { return checkRow(ui, c.label, c.ok, c.detail); }))))
    ]));
  }

  return { render: render };
})();
