/** QVM Dashboard - ptv view (M1 stub; filled in later milestones). */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.ptv = (function () {
  'use strict';
  function render(main) {
    var ui = window.QVM.ui;
    main.appendChild(ui.el('section', { 'class': 'panel' }, [
      ui.el('h2', { text: 'Pad to Via' }),
      ui.el('p', { text: 'Under construction.' })
    ]));
  }
  return { render: render };
})();
