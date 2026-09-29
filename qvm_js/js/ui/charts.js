/**
 * Metrology Request Tracker - ui/charts.js  (copied from ABF Tracker v2)
 *
 * Chart.js wrapper: one theme config for every chart (vendor/chart.umd.min.js).
 * Adds to QVM.ui (see ui/core.js for the load order).
 *
 * Rule: user text never reaches innerHTML. Use el()/text() or esc().
 */
(function (ui) {
  'use strict';

  var el = ui.el;
  var hideTip = ui.hideTip;
  var icon = ui.icon;
  var mount = ui.mount;
  var placeTip = ui.placeTip;
  var reducedMotion = ui.reducedMotion;

  /* ------------------------------------------------------------------ *
   * Charts (Chart.js, vendor/chart.umd.min.js)
   *
   * One theme config for every chart. Colours come from the CSS tokens of
   * the element the chart sits in, so a chart follows Dark / Light / HC and
   * a nested theme scope. Tooltips are the same panel-style card as the
   * rest of the app. Bars grow from the axis, lines draw in point by point.
   * Without the vendor file, charts show a notice instead.
   * ------------------------------------------------------------------ */

  var CHART_TOKENS = ['fg', 'fg-muted', 'fg-faint', 'line', 'line-strong', 'surface', 'surface-2',
                      'accent', 'ok', 'warning', 'critical', 'expired', 'blocked', 'danger',
                      'c-blue', 'c-teal', 'c-pink'];
  // categorical series order (tools, projects): distinct hues from the tokens
  var CHART_SERIES = ['accent', 'c-teal', 'warning', 'c-blue', 'ok', 'c-pink', 'blocked'];

  var liveCharts = [];

  function hasChartJs() { return typeof window.Chart === 'function'; }

  function parseRgb(s) {
    var m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return [128, 128, 128, 1];
    var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }

  /**
   * Resolve the colour tokens in effect at `scope` (defaults to <html>).
   * Returns {rgb: {name: [r,g,b,a]}, color(name), alpha(name, a), series(i), font, mono}.
   */
  function chartTheme(scope) {
    var host = scope && scope.isConnected ? scope : document.body;
    var probe = el('i', { style: { position: 'absolute', visibility: 'hidden' } });
    host.appendChild(probe);
    var rgb = {};
    CHART_TOKENS.forEach(function (n) {
      probe.style.color = 'var(--' + n + ')';
      rgb[n] = parseRgb(getComputedStyle(probe).color);
    });
    host.removeChild(probe);
    var theme = {
      rgb: rgb,
      alpha: function (name, a) {
        var c = rgb[name] || parseRgb(name);
        return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (a === undefined ? c[3] : a) + ')';
      },
      color: function (name) { return theme.alpha(name); },
      series: function (i) { return CHART_SERIES[i % CHART_SERIES.length]; },
      font: getComputedStyle(document.documentElement).getPropertyValue('--font-ui').trim() || 'system-ui',
      mono: getComputedStyle(document.documentElement).getPropertyValue('--font-mono').trim() || 'monospace'
    };
    return theme;
  }

  /**
   * A vertical (or horizontal) gradient for a dataset fill, as a scriptable
   * option: backgroundColor: ui.chartGradient(theme, 'accent', .55, .05)
   */
  function chartGradient(theme, name, fromA, toA, horizontal) {
    return function (ctx) {
      var area = ctx.chart.chartArea;
      if (!area) return theme.alpha(name, fromA);
      var g = horizontal
        ? ctx.chart.ctx.createLinearGradient(area.left, 0, area.right, 0)
        : ctx.chart.ctx.createLinearGradient(0, area.bottom, 0, area.top);
      g.addColorStop(0, theme.alpha(name, toA));      // at the axis
      g.addColorStop(1, theme.alpha(name, fromA));
      return g;
    };
  }

  /** Line draw-in, point by point (Chart.js "progressive line"). */
  function progressiveAnimation(points) {
    var step = 900 / Math.max(1, points);
    function prevY(ctx) {
      if (ctx.index === 0) return ctx.chart.scales.y ? ctx.chart.scales.y.getPixelForValue(0) : 0;
      var meta = ctx.chart.getDatasetMeta(ctx.datasetIndex);
      var prev = meta.data[ctx.index - 1];
      return prev ? prev.getProps(['y'], true).y : 0;
    }
    return {
      x: { type: 'number', easing: 'linear', duration: step, from: NaN,
           delay: function (ctx) { if (ctx.type !== 'data' || ctx.xStarted) return 0; ctx.xStarted = true; return ctx.index * step; } },
      y: { type: 'number', easing: 'linear', duration: step, from: prevY,
           delay: function (ctx) { if (ctx.type !== 'data' || ctx.yStarted) return 0; ctx.yStarted = true; return ctx.index * step; } }
    };
  }

  function mergeDeep(target, src) {
    Object.keys(src || {}).forEach(function (k) {
      var v = src[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && typeof v !== 'function' &&
          target[k] && typeof target[k] === 'object' && !Array.isArray(target[k])) {
        mergeDeep(target[k], v);
      } else {
        target[k] = v;
      }
    });
    return target;
  }

  /** The panel-style tooltip, drawn in the shared tip card. */
  function chartTooltip(theme, o) {
    return function (context) {
      var tip = context.tooltip;
      if (!tip || tip.opacity === 0) { hideTip(); return; }
      var rows = (tip.dataPoints || []).map(function (dp) {
        var ds = dp.dataset;
        var swatch = ds.tipColor || (typeof ds.borderColor === 'string' ? ds.borderColor : theme.color('accent'));
        if (Array.isArray(ds.tipColor)) swatch = ds.tipColor[dp.dataIndex];
        var value = o.format ? o.format(dp.raw, dp) : dp.formattedValue;
        return el('div', { class: 'tip-row' }, [
          el('span', { class: 'tip-key' }, [el('i', { class: 'tip-swatch', style: { background: swatch } }),
            ds.label || dp.label || '']),
          el('b', { text: value })
        ]);
      });
      var r = context.chart.canvas.getBoundingClientRect();
      var x = r.left + tip.caretX, y = r.top + tip.caretY;
      placeTip({ left: x - 1, right: x + 1, top: y - 4, bottom: y + 4, width: 2, height: 8 },
        [el('div', { class: 'tip-title', text: (tip.title || []).join(' ') })].concat(rows,
          o.onPick ? [el('div', { class: 'tip-hint', text: 'Click to open' })] : []), context.chart.canvas);
    };
  }

  /**
   * chart(build, {height, label, onPick, format, drawIn, expand})
   *   build(theme) -> Chart.js config {type, data, options}. It is called
   *   again when the theme changes, so read colours from `theme`.
   *   onPick(index, datasetIndex, chart) makes points/bars clickable.
   *   format(raw, dataPoint) formats tooltip values.
   *   expand: true or {title, icon} adds a full-screen button (title defaults to label); the big chart is the
   *   same build at the dialog's size.
   * Returns {node, chart(), refresh(), destroy()}.
   */
  function chart(build, o) {
    o = o || {};
    var box = el('div', { class: 'chart-box', style: { height: (o.height || 240) + 'px' } });
    if (!hasChartJs()) {
      mount(box, el('div', { class: 'chart-missing' }, [
        icon('chart', 20),
        el('div', {}, [el('b', { text: 'Chart library not found' }),
          el('span', { text: 'Put chart.umd.min.js (Chart.js 4) in the vendor folder.' })])
      ]));
      return { node: box, chart: function () { return null; }, refresh: function () {}, destroy: function () {} };
    }
    var canvas = el('canvas', { role: 'img', 'aria-label': o.label || 'Chart' });
    box.appendChild(canvas);
    if (o.expand === true) o.expand = {};
    if (o.expand) {
      box.classList.add('has-expand');
      box.appendChild(el('button', { class: 'btn-icon chart-expand', type: 'button',
        'aria-label': 'Full screen: ' + (o.expand.title || o.label || 'chart'), title: 'Full screen',
        onclick: function () { expandChart(build, o); } }, icon('expand', 15)));
    }
    var instance = null;
    var entry = { box: box, create: create, destroy: destroy };

    function config(animate) {
      var theme = chartTheme(box);
      var cfg = build(theme);
      var type = cfg.type;
      var scaled = type !== 'doughnut' && type !== 'pie' && type !== 'polarArea';
      var defaults = {
        responsive: true, maintainAspectRatio: false,
        color: theme.color('fg-muted'),
        font: { family: theme.font, size: 12 },
        layout: { padding: { top: 4, right: 4, bottom: 0, left: 0 } },
        interaction: { mode: type === 'line' || type === 'scatter' ? 'nearest' : 'index', intersect: type === 'scatter' },
        animation: animate ? { duration: 900, easing: 'easeOutQuart' } : false,
        plugins: {
          legend: { position: 'bottom', labels: { color: theme.color('fg-muted'), usePointStyle: true,
                    pointStyle: 'rectRounded', boxWidth: 8, boxHeight: 8, padding: 14,
                    font: { family: theme.font, size: 12 } } },
          tooltip: { enabled: false, external: chartTooltip(theme, o) }
        }
      };
      if (type === 'doughnut') defaults.cutout = '68%';
      // Legend swatch = the series colour. Chart.js would take it from the
      // first point, which is wrong when points are coloured (pass/fail) or
      // the fill is a gradient.
      if (scaled) {
        defaults.plugins.legend.labels.generateLabels = function (ch) {
          return window.Chart.defaults.plugins.legend.labels.generateLabels(ch).map(function (item) {
            var c = (ch.data.datasets[item.datasetIndex] || {}).tipColor;
            if (typeof c === 'string') { item.fillStyle = c; item.strokeStyle = c; }
            return item;
          });
        };
      }
      if (animate && type === 'line' && o.drawIn !== false) {
        var n = 0;
        (cfg.data.datasets || []).forEach(function (d) { n = Math.max(n, (d.data || []).length); });
        defaults.animations = progressiveAnimation(n);
      }
      if (o.onPick) {
        defaults.onClick = function (evt, els, ch) {
          if (els && els.length) o.onPick(els[0].index, els[0].datasetIndex, ch);
        };
        defaults.onHover = function (evt, els) { canvas.style.cursor = els && els.length ? 'pointer' : 'default'; };
      }
      var options = mergeDeep(defaults, cfg.options || {});
      if (scaled) {
        options.scales = options.scales || { x: {}, y: {} };
        Object.keys(options.scales).forEach(function (k) {
          options.scales[k] = mergeDeep({
            grid: { color: theme.alpha('line'), drawTicks: false },
            border: { color: theme.alpha('line-strong') },
            ticks: { color: theme.color('fg-muted'), padding: 6, font: { family: theme.mono, size: 11 } },
            title: { color: theme.color('fg-muted'), font: { family: theme.font, size: 11 } }
          }, options.scales[k]);
        });
      }
      // datasets: rounded bars, smooth lines, visible points on hover only
      (cfg.data.datasets || []).forEach(function (d) {
        var t = d.type || type;
        if (t === 'bar' && d.borderRadius === undefined) d.borderRadius = 4;
        if (t === 'bar' && d.maxBarThickness === undefined) d.maxBarThickness = 38;
        if (t === 'line') {
          if (d.tension === undefined) d.tension = 0.3;
          if (d.pointRadius === undefined) d.pointRadius = 2.5;
          if (d.pointHoverRadius === undefined) d.pointHoverRadius = 5;
          if (d.borderWidth === undefined) d.borderWidth = 2;
        }
        if (t === 'doughnut' && d.borderColor === undefined) { d.borderColor = theme.color('surface'); d.borderWidth = 2; }
      });
      return { type: type, data: cfg.data, options: options, plugins: cfg.plugins || [] };
    }

    function create(animate) {
      if (instance) instance.destroy();
      instance = new window.Chart(canvas, config(animate));
    }

    // Create once the box is in the document (tokens need a real scope).
    var tries = 0;
    (function wait() {
      if (box.isConnected) { sweepCharts(); create(!reducedMotion()); liveCharts.push(entry); return; }
      if (++tries < 120) requestAnimationFrame(wait);
    })();

    function destroy() {
      if (instance) instance.destroy();
      instance = null;
      liveCharts = liveCharts.filter(function (e) { return e !== entry; });
    }
    return {
      node: box,
      chart: function () { return instance; },
      refresh: function () { if (instance) create(false); },
      destroy: destroy
    };
  }

  /** Destroy charts whose page was re-rendered away, so they never leak. */
  /** The same chart, full screen in a dialog. */
  function expandChart(build, o) {
    var big = {};
    Object.keys(o).forEach(function (k) { big[k] = o[k]; });
    big.expand = null;
    big.height = Math.max(320, window.innerHeight - 190);
    ui.dialog({ title: o.expand.title || o.label || 'Chart', icon: o.expand.icon || 'chart', cls: 'chart-full',
                body: chart(build, big).node });
  }

  function sweepCharts() {
    liveCharts.slice().forEach(function (e) { if (!e.box.isConnected) e.destroy(); });
  }

  /** Rebuild every live chart with the current theme (call after a theme change). */
  function rethemeCharts() {
    sweepCharts();
    liveCharts.forEach(function (e) { e.create(false); });
  }

  ui.chart = chart;
  ui.chartGradient = chartGradient;
  ui.chartTheme = chartTheme;
  ui.hasChartJs = hasChartJs;
  ui.rethemeCharts = rethemeCharts;
})(window.QVM.ui);
