/** QVM Dashboard - ptv view: delegates to the shared QC renderer (M6). */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.ptv = (function () {
  'use strict';
  function render(main) { window.QVM.qc.renderQcView(main, 'Pad to Via'); }
  return { render: render };
})();
