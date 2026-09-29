/**
 * QVM Dashboard - app.js shell (M1)
 *
 * Hash router, collapsible nav, theme picker. No gate, no identity, no save
 * lamp: this is an analyst-only tool, uploads live in session memory and only
 * tolerances/theme persist (localStorage). Vendor libs (Chart.js, SheetJS)
 * arrive in M2; views fill in M6-M8.
 */
window.QVM = window.QVM || {};
window.QVM.app = (function () {
  'use strict';

  var NAV = [
    { hash: '#/panel-map',      label: 'Panel Map',     view: 'panelmap', milestone: 8 },
    { hash: '#/pad-to-via',     label: 'Pad to Via',    view: 'ptv',      milestone: 6 },
    { hash: '#/via-to-pad',     label: 'Via to Pad',    view: 'vtp',      milestone: 6 },
    { hash: '#/core-shrinkage',  label: 'Core Shrinkage', view: 'coreshk', milestone: 6 },
    { hash: '#/health',         label: 'Health',        view: 'health',   milestone: 10 },
    { hash: '#/help',           label: 'Help',          view: 'help',     milestone: 1 }
  ];

  function views() { return window.QVM.views || {}; }

  function currentRoute() {
    var h = String(window.location.hash || '#/panel-map');
    for (var i = 0; i < NAV.length; i++) {
      if (h === NAV[i].hash || h.indexOf(NAV[i].hash + '/') === 0) return NAV[i];
    }
    return NAV[0];
  }

  function renderNav(route) {
    var ui = window.QVM.ui;
    var host = document.getElementById('navItems');
    host.textContent = '';
    NAV.forEach(function (item) {
      var a = ui.el('a', {
        href: item.hash,
        'class': 'nav-item' + (item.hash === route.hash ? ' is-active' : ''),
        'aria-current': item.hash === route.hash ? 'page' : null
      }, [ui.el('span', { 'class': 'nav-label', text: item.label })]);
      host.appendChild(a);
    });
  }

  function render(route) {
    renderNav(route);
    var main = document.getElementById('main');
    main.textContent = '';
    var v = views()[route.view];
    if (v && typeof v.render === 'function') {
      v.render(main);
    } else {
      renderStub(main, route.label, route.milestone);
    }
    if (document.activeElement && document.activeElement.blur) {
      try { document.activeElement.blur(); } catch (e) { /* noop */ }
    }
  }

  function renderStub(main, label, milestone) {
    var ui = window.QVM.ui;
    main.appendChild(ui.el('section', { 'class': 'panel' }, [
      ui.el('h2', { text: label }),
      ui.el('p', { text: 'Coming in milestone ' + milestone + '.' })
    ]));
  }

  function cycleTheme() {
    var t = window.QVM.themes;
    var order = t.list.map(function (x) { return x.key; });
    var cur = document.documentElement.getAttribute('data-theme') || t.DEFAULT;
    t.apply(order[(order.indexOf(cur) + 1) % order.length]);
  }

  function onAction(ev) {
    var t = ev.target && ev.target.closest ? ev.target.closest('[data-action]') : null;
    if (!t) return;
    var action = t.getAttribute('data-action');
    if (action === 'cycle-theme') { cycleTheme(); }
    else if (action === 'nav-collapse') {
      document.getElementById('nav').classList.toggle('is-collapsed');
    }
  }

  function onHash() { render(currentRoute()); }

  function init() {
    window.QVM.themes.install();
    document.getElementById('shell').hidden = false;
    document.getElementById('brandVer').textContent =
      window.QVM.config.version;
    document.addEventListener('click', onAction);
    window.addEventListener('hashchange', onHash);
    if (!window.location.hash) window.location.hash = '#/panel-map';
    render(currentRoute());
  }

  return { init: init, NAV: NAV, currentRoute: currentRoute };
})();

document.addEventListener('DOMContentLoaded', function () {
  window.QVM.app.init();
});
