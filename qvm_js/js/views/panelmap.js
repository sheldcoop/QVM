/**
 * QVM Dashboard - panelmap view (M8)
 *
 * Reference panel map plus the distortion legend. Per-site distortion
 * overlays arrive with the measurement data (PtV/VtP quiver charts);
 * this tab is the static orientation reference, like the Python app.
 */
window.QVM = window.QVM || {};
window.QVM.views = window.QVM.views || {};
window.QVM.views.panelmap = (function () {
  'use strict';
  function render(main) {
    var ui = window.QVM.ui;
    main.appendChild(ui.el('h2', { text: 'Panel Map' }));
    var img = ui.el('img', { src: 'assets/Panel_Map.png',
      alt: 'Panel fiducial map: quarters UL, LL, LR, UR with grid IDs 11-44',
      style: { maxWidth: '100%', height: 'auto' } });
    main.appendChild(ui.el('section', { class: 'panel' }, [
      ui.el('h2', { text: 'Reference map' }),
      img,
      ui.el('p', { text: 'Quarters run anticlockwise UL → LL → LR → UR, ' +
        'grid IDs 11–44. The ABF distortion map on each process tab plots ' +
        'sites on this 1–4 grid.' })
    ]));
  }
  return { render: render };
})();
