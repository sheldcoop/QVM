/** QVM Dashboard - vtp view: delegates to the shared QC renderer (M6). */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.vtp = (function () {
  'use strict';
  function render(main) { window.QVM.qc.renderQcView(main, 'Via to Pad'); }
  return { render: render };
})();
