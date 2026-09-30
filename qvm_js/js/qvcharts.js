/**
 * QVM Dashboard - qvcharts.js (M7)
 *
 * Chart.js config builders for the QVM analytics: bullseye scatter (canvas
 * ring plugin), per-site SC bars, per-quarter box plot (floating bars +
 * median ticks). Each builder is build(theme) -> config, called again on
 * theme change, so colours resolve from the live theme every time.
 *
 * Zone → theme token map mirrors Python's Catppuccin zones
 * (blue/green/teal/peach/red). No Chart.js import: the ui.chart wrapper
 * constructs; unit tests call builders with a stub theme.
 */
window.QVM = window.QVM || {};
window.QVM.charts = (function () {
  'use strict';

  var ZONE_TOKENS = {
    exceptional: 'accent', excellent: 'ok', good: 'c-teal',
    acceptable: 'warning', fail: 'critical'
  };
  var QUARTER_TOKENS = { UL: 'c-teal', LL: 'warning', LR: 'ok', UR: 'c-pink' };
  var QUARTERS = ['UL', 'LL', 'LR', 'UR'];

  function rowsWithSc(rows) {
    return (rows || []).filter(function (r) {
      return r.dx !== null && r.dx !== undefined && r.dy !== null && r.dy !== undefined &&
             r.sc !== null && r.sc !== undefined;
    });
  }

  /** Inline plugin: tolerance rings + crosshair behind the scatter. */
  var ringsPlugin = {
    id: 'qvmRings',
    beforeDraw: function (chart) {
      var o = chart.config.options.plugins && chart.config.options.plugins.qvmRings;
      if (!o || !o.rings || typeof window === 'undefined') return;
      var area = chart.chartArea;
      if (!area) return;
      var x = chart.scales.x, y = chart.scales.y;
      var cx = x.getPixelForValue(0), cy = y.getPixelForValue(0);
      var ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = o.cross;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(area.left, cy); ctx.lineTo(area.right, cy);
      ctx.moveTo(cx, area.top); ctx.lineTo(cx, area.bottom);
      ctx.stroke();
      o.rings.forEach(function (r, i) {
        var rx = x.getPixelForValue(r) - cx;
        if (rx <= 0) return;
        ctx.strokeStyle = o.colors[i];
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, rx, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.restore();
    }
  };

  function bullseyeBuild(rows, rings) {
    var pts = rowsWithSc(rows).map(function (r) {
      var scUm = r.sc * 1000;
      var zone = window.QVM.domain.zoneOf(scUm, rings);
      return { x: r.dx * 1000, y: r.dy * 1000, zone: zone,
               tip: (r.location || '?') + ' · Grid ' + (r.gridId === null || r.gridId === undefined ? '—' : r.gridId) +
                    ' · SC ' + scUm.toFixed(2) + ' µm' };
    });
    var extreme = 0;
    pts.forEach(function (p) {
      extreme = Math.max(extreme, Math.abs(p.x), Math.abs(p.y));
    });
    var spread = Math.max(rings.acceptable * 1.15, extreme * 1.1);
    return function (t) {
      return {
        type: 'scatter',
        data: { datasets: [{ label: 'Sites', data: pts,
          backgroundColor: pts.map(function (p) { return t.color(ZONE_TOKENS[p.zone]); }),
          pointRadius: 4, pointHoverRadius: 6 }] },
        options: {
          aspectRatio: 1,
          scales: {
            x: { min: -spread, max: spread, title: { display: true, text: 'DX (µm)' } },
            y: { min: -spread, max: spread, title: { display: true, text: 'DY (µm)' } }
          },
          plugins: { qvmRings: {
            rings: [rings.exceptional, rings.excellent, rings.good, rings.acceptable],
            colors: [t.color('accent'), t.color('ok'), t.color('c-teal'), t.color('warning')],
            cross: t.alpha('fg-muted', 0.5)
          } }
        },
        plugins: [ringsPlugin]
      };
    };
  }

  function siteBarsBuild(rows, rings) {
    var D = window.QVM.domain;
    var items = rowsWithSc(rows)
      .filter(function (r) { return r.gridId !== null && r.gridId !== undefined; })
      .sort(function (a, b) { return a.gridId - b.gridId; })
      .map(function (r) {
        return { label: String(r.gridId), scUm: r.sc * 1000,
                 zone: D.zoneOf(r.sc * 1000, rings),
                 tip: (r.location || '?') + ' · SC ' + (r.sc * 1000).toFixed(2) + ' µm' };
      });
    return function (t) {
      return {
        type: 'bar',
        data: { labels: items.map(function (d) { return d.label; }),
          datasets: [{ label: 'SC (µm)', data: items.map(function (d) { return d.scUm; }),
            backgroundColor: items.map(function (d) { return t.color(ZONE_TOKENS[d.zone]); }) }] },
        options: { scales: { y: { title: { display: true, text: 'SC (µm)' } },
                             x: { title: { display: true, text: 'Grid ID' } } } }
      };
    };
  }

  function boxBuild(rows) {
    var D = window.QVM.domain;
    var present = QUARTERS.filter(function (q) {
      return rows.some(function (r) {
        return String(r.location || '').split('_')[0] === q &&
               r.sc !== null && r.sc !== undefined;
      });
    });
    var boxes = present.map(function (q) {
      return { q: q, box: D.boxStats(rows
        .filter(function (r) { return String(r.location || '').split('_')[0] === q; })
        .map(function (r) { return r.sc * 1000; })) };
    });
    return function (t) {
      var datasets = [{
        type: 'bar', label: 'Range',
        data: boxes.map(function (b) { return [b.box.min, b.box.max]; }),
        backgroundColor: boxes.map(function (b) { return t.alpha(QUARTER_TOKENS[b.q], 0.3); }),
        barPercentage: 0.18, categoryPercentage: 1
      }];
      boxes.forEach(function (b) {
        datasets.push({ type: 'bar', label: b.q,
          data: boxes.map(function (o) { return o.q === b.q ? [o.box.q1, o.box.q3] : null; }),
          backgroundColor: t.color(QUARTER_TOKENS[b.q]), barPercentage: 0.55 });
      });
      datasets.push({ type: 'scatter', label: 'Median',
        data: boxes.map(function (b) { return { x: b.q, y: b.box.median }; }),
        backgroundColor: t.color('fg'), pointStyle: 'line', radius: 9, borderWidth: 3 });
      return {
        type: 'bar',
        data: { labels: present, datasets: datasets },
        options: {
          scales: { y: { title: { display: true, text: 'SC (µm)' } } },
          plugins: { legend: { labels: { filter: function (item) {
            return present.indexOf(item.text) !== -1 || item.text === 'Median';
          } } } }
        }
      };
    };
  }

  return {
    ZONE_TOKENS: ZONE_TOKENS,
    QUARTER_TOKENS: QUARTER_TOKENS,
    ringsPlugin: ringsPlugin,
    bullseyeBuild: bullseyeBuild,
    siteBarsBuild: siteBarsBuild,
    boxBuild: boxBuild
  };
})();
