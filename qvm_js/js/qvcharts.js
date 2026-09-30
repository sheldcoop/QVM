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

  var ARROW_TOKENS = {
    Expansion: 'critical', Contraction: 'c-blue', Twist: 'warning', Offset: 'accent'
  };

  /**
   * ABF distortion quiver. Sites sit on the 1-4 panel grid; arrows show the
   * DX/DY shift × multiplier (min-length floor like Python). The plugin draws
   * arrows, grid labels, crosshair, summary card, and legend — all canvas, so
   * M9 PNG export captures the whole chart.
   */
  function quiverBuild(rows, settings, multiplier) {
    var D = window.QVM.domain;
    var diag = (settings && settings.DIAGNOSTICS) || {};
    function num(v, fallback) { var n = parseFloat(v); return isNaN(n) ? fallback : n; }
    var cx = num(diag.panel_center_x, 255), cy = num(diag.panel_center_y, 257.5);
    var minArrow = num(diag.quiver_min_arrow_length, 0.05);
    var cfg = { expansionThr: num(diag.quiver_expansion_dot_threshold, 0.5),
                twistDotThr: num(diag.quiver_twist_dot_threshold, 0.2),
                twistMagUm: num(diag.quiver_twist_magnitude_um, 10) };
    var gridPos = (settings && settings.GRID_PLOT_POSITIONS) || {};

    var dots = [];
    (rows || []).forEach(function (r) {
      if (r.dx === null || r.dx === undefined || r.dy === null || r.dy === undefined) return;
      var gp = gridPos[r.gridId];
      if (!gp) return;
      var dxUm = r.dx * 1000, dyUm = r.dy * 1000;
      var mag = Math.hypot(dxUm, dyUm);
      var dxS = dxUm * multiplier * 0.001, dyS = dyUm * multiplier * 0.001;
      var len = Math.hypot(dxS, dyS);
      if (len > 0 && len < minArrow) { dxS *= minArrow / len; dyS *= minArrow / len; }
      var hasCoords = r.coordX !== null && r.coordX !== undefined &&
                      r.coordY !== null && r.coordY !== undefined;
      var px = hasCoords ? r.coordX - cx : gp[0] - 2.5;
      var py = hasCoords ? r.coordY - cy : gp[1] - 2.5;
      var pattern = D.classifyQuiver(dxUm, dyUm, px, py, mag, cfg);
      dots.push({ x: gp[0], y: gp[1], dx: dxS, dy: dyS, pattern: pattern,
                  grid: String(r.gridId), location: r.location || '?',
                  tip: (r.location || '?') + ' · Grid ' + r.gridId + ' · ' + pattern +
                       ' · DX ' + dxUm.toFixed(2) + ' µm · DY ' + dyUm.toFixed(2) +
                       ' µm · Mag ' + mag.toFixed(2) + ' µm' });
    });
    var counts = { Expansion: 0, Contraction: 0, Twist: 0, Offset: 0 };
    dots.forEach(function (d) { counts[d.pattern]++; });

    return function (t) {
      return {
        type: 'scatter',
        data: { datasets: [{ label: 'Sites', data: dots,
          backgroundColor: dots.map(function (d) { return t.color(ARROW_TOKENS[d.pattern]); }),
          pointRadius: 5, pointHoverRadius: 7 }] },
        options: {
          aspectRatio: 1,
          scales: {
            x: { min: 0.5, max: 4.5, ticks: { display: false },
                 title: { display: true, text: 'Panel X (Grid Column)' } },
            y: { min: 0.5, max: 4.5, ticks: { display: false },
                 title: { display: true, text: 'Panel Y (Grid Row)' } }
          },
          plugins: { qvmQuiver: {
            multiplier: multiplier, counts: counts, total: dots.length,
            arrows: dots.map(function (d) {
              return { x: d.x, y: d.y, dx: d.dx, dy: d.dy,
                       color: t.color(ARROW_TOKENS[d.pattern]), grid: d.grid };
            }),
            legend: ['Expansion', 'Contraction', 'Twist', 'Offset'].map(function (l) {
              return { label: l, color: t.color(ARROW_TOKENS[l]) };
            }),
            cross: t.alpha('fg-muted', 0.5), text: t.color('fg'), font: t.font
          } }
        },
        plugins: [quiverPlugin]
      };
    };
  }

  /** Inline plugin: arrows, grid labels, crosshair, summary card, legend. */
  var quiverPlugin = {
    id: 'qvmQuiver',
    beforeDraw: function (chart) {
      var o = chart.config.options.plugins && chart.config.options.plugins.qvmQuiver;
      if (!o || !o.arrows || typeof window === 'undefined') return;
      var area = chart.chartArea;
      if (!area) return;
      var x = chart.scales.x, y = chart.scales.y;
      var ctx = chart.ctx;
      ctx.save();
      // Crosshair through the panel middle.
      var mx = x.getPixelForValue(2.5), my = y.getPixelForValue(2.5);
      ctx.strokeStyle = o.cross;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(area.left, my); ctx.lineTo(area.right, my);
      ctx.moveTo(mx, area.top); ctx.lineTo(mx, area.bottom);
      ctx.stroke();
      // Arrows with heads.
      o.arrows.forEach(function (a) {
        var x0 = x.getPixelForValue(a.x), y0 = y.getPixelForValue(a.y);
        var x1 = x.getPixelForValue(a.x + a.dx), y1 = y.getPixelForValue(a.y + a.dy);
        var ang = Math.atan2(y1 - y0, x1 - x0);
        ctx.strokeStyle = a.color;
        ctx.fillStyle = a.color;
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
        var head = 8;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x1 - head * Math.cos(ang - 0.42), y1 - head * Math.sin(ang - 0.42));
        ctx.lineTo(x1 - head * Math.cos(ang + 0.42), y1 - head * Math.sin(ang + 0.42));
        ctx.closePath(); ctx.fill();
        // Grid label above the dot.
        ctx.font = '10px ' + (o.font || 'system-ui');
        ctx.textAlign = 'center';
        ctx.fillText(a.grid, x0, y0 - 12);
      });
      // Summary card top-left, legend bottom-centre.
      ctx.fillStyle = o.text;
      ctx.textAlign = 'left';
      ctx.font = '11px ' + (o.font || 'system-ui');
      ctx.fillText('n ' + o.total + '  •  Exp/Con ' +
        (o.counts.Expansion + o.counts.Contraction) + '  •  Twist ' +
        o.counts.Twist + '  •  Offset ' + o.counts.Offset, area.left + 8, area.top + 16);
      // Legend bottom-centre: coloured dot + label per pattern.
      ctx.textAlign = 'left';
      ctx.font = '10px ' + (o.font || 'system-ui');
      var items = o.legend || [];
      var widths = items.map(function (it) { return ctx.measureText('● ' + it.label + '   ').width; });
      var totalW = widths.reduce(function (a2, b) { return a2 + b; }, 0);
      var lx = area.left + (area.right - area.left - totalW) / 2, ly = area.bottom - 10;
      items.forEach(function (it, i) {
        ctx.fillStyle = it.color;
        ctx.fillText('●', lx, ly);
        var dotW = ctx.measureText('● ').width;
        ctx.fillStyle = o.text;
        ctx.fillText(it.label, lx + dotW, ly);
        lx += widths[i];
      });
      ctx.restore();
    }
  };

  return {
    ZONE_TOKENS: ZONE_TOKENS,
    QUARTER_TOKENS: QUARTER_TOKENS,
    ARROW_TOKENS: ARROW_TOKENS,
    ringsPlugin: ringsPlugin,
    quiverPlugin: quiverPlugin,
    bullseyeBuild: bullseyeBuild,
    siteBarsBuild: siteBarsBuild,
    boxBuild: boxBuild,
    quiverBuild: quiverBuild
  };
})();
