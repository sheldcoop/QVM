/**
 * js/ui-kit.js - dev only. Renders every copied UI component into ui-kit.html
 * for eyeballing in the browser, in one theme at a time (picker in the bar).
 * Grows per milestone as components land; never loaded by index.html.
 */
window.QVM = window.QVM || {};
window.QVM.kit = (function () {
  'use strict';

  var ui, TH;

  function el(tag, attrs, kids) { return ui.el(tag, attrs, kids); }

  function sec(title, note, children) {
    return el('section', { class: 'kit-sec' }, [
      el('h2', { text: title }),
      note ? el('p', { class: 'kit-note', text: note }) : null,
      children
    ]);
  }

  function labelled(label, node) {
    return el('div', {}, [el('div', { class: 'kit-label', text: label }), node]);
  }

  function bar() {
    var bar = document.getElementById('kitBar');
    bar.textContent = '';
    var h1 = el('h1', {}, [el('span', { text: 'QVM Dashboard UI kit' })]);
    var sel = document.createElement('select');
    sel.id = 'kitTheme';
    sel.setAttribute('aria-label', 'Theme');
    var all = document.createElement('option');
    all.value = 'all'; all.textContent = 'All themes side by side';
    sel.appendChild(all);
    TH.list.forEach(function (t) {
      var o = document.createElement('option');
      o.value = t.key; o.textContent = t.name;
      sel.appendChild(o);
    });
    sel.value = document.documentElement.getAttribute('data-theme') || TH.DEFAULT;
    sel.addEventListener('change', function () { render(sel.value); });
    bar.appendChild(h1);
    bar.appendChild(el('span', { class: 'spacer' }));
    bar.appendChild(sel);
  }

  function gallery() {
    return [
      sec('Panel', null, el('div', { class: 'kit-grid' }, [
        labelled('Status + action', ui.panel({ title: 'Measurement', icon: 'gauge', status: 'ok',
          body: el('p', { text: 'A panel with a status glow and one action.' }),
          actions: [ui.button('Export', { kind: 'primary' })] }).node)
      ])),
      sec('Buttons', null, el('div', { class: 'qvm-row' }, [
        ui.button('Default'), ui.button('Primary', { kind: 'primary' }),
        ui.button('Danger', { kind: 'danger' }), ui.button('Ghost', { kind: 'ghost' })
      ])),
      sec('Fields + form', null, el('div', { class: 'kit-grid' }, [
        labelled('Text + number', el('div', {}, [
          ui.field({ label: 'Panel', value: '20' }).node,
          ui.field({ label: 'Tolerance (µm)', type: 'number', value: 10 }).node
        ])),
        labelled('Segmented + toggle', el('div', {}, [
          ui.segmented({ label: 'Side', value: 'F', options: [
            { value: 'F', label: 'Front' }, { value: 'B', label: 'Back' }] }).node,
          ui.toggle({ label: 'Show outliers', checked: true }).node
        ]))
      ])),
      sec('Chips + KPI', null, el('div', { class: 'qvm-row' }, [
        ui.statusChip('ok'), ui.statusChip('warning'), ui.statusChip('expired'),
        ui.kpiTile({ label: 'Mean SC', value: '4.2 µm', status: 'ok' }).node
      ])),
      sec('Table + tabs', null, el('div', {}, [
        ui.tabs([{ key: 'a', label: 'Quality' }, { key: 'b', label: 'Analytics' }], function () {}).node,
        el('div', { class: 'table-wrap' }, el('table', { class: 'grid' }, [
          el('tr', {}, [el('th', { text: 'Grid' }), el('th', { text: 'SC (µm)' })]),
          el('tr', {}, [el('td', { text: '11' }), el('td', { text: '4.2' })])
        ]))
      ])),
      sec('Glyphs', 'One per tool, live state', el('div', { class: 'kit-glyphs' },
        ui.GLYPHS.map(function (g) {
          return [el('span', { text: g.label }), ui.toolGlyph(g.key, { state: 'live', size: 40 })];
        }).reduce(function (a, b) { return a.concat(b); }, []))),
      sec('Chart', 'Needs vendor/chart.umd.min.js, else a notice', el('div', {},
        ui.chart(function (t) {
          return { type: 'bar', data: { labels: ['a', 'b'],
            datasets: [{ label: 'x', data: [1, 2], backgroundColor: t.color('accent') }] }, options: {} };
        }, { height: 200 }).node))
    ];
  }

  function render(mode) {
    var root = document.getElementById('kitRoot');
    root.textContent = '';
    if (mode === 'all') {
      root.classList.add('all');
      TH.list.forEach(function (t) {
        var scope = el('div', { class: 'theme-scope' }, [
          el('div', { class: 'kit-col-title', text: t.name })
        ]);
        TH.setOn(scope, t.key);
        gallery().forEach(function (s) { scope.appendChild(s); });
        root.appendChild(scope);
      });
    } else {
      root.classList.remove('all');
      TH.apply(mode);
      gallery().forEach(function (s) { root.appendChild(s); });
    }
  }

  function init() {
    ui = window.QVM.ui;
    TH = window.QVM.themes;
    bar();
    render('all');
    document.getElementById('kitTheme').addEventListener('change', function (e) {
      render(e.target.value);
    });
  }

  return { init: init };
})();

document.addEventListener('DOMContentLoaded', function () {
  window.QVM.themes.install();
  window.QVM.kit.init();
});
