/** QVM Dashboard - coreshk view: delegates to the shared QC renderer (M6). */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.coreshk = (function () {
  'use strict';
  function render(main) { window.QVM.qc.renderCsView(main); }
  return { render: render };
})();
