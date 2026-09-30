/**
 * QVM Dashboard - domain.js
 *
 * Rules & maths, pure functions only. No DOM, no store, no Date.now():
 * time (when needed) arrives as `now_ts`. Measurement units ride in suffixes
 * (`_um`, `_mm`, `_ppm`), mirroring the Python app's mm-storage convention.
 *
 * M1: namespace + version only. M4 fills the statistics (annular ring, SC,
 * zones, QP shrinkage); M5 the affine geometry.
 */
window.QVM = window.QVM || {};
window.QVM.domain = (function () {
  'use strict';

  var SCHEMA_VERSION = 1;

  /**
   * Annular ring (mm): (pad/2) - (via/2) - sc. Null when any input is missing.
   * Port of Python calculate_annular_ring; row uses internal keys (D6).
   */
  function annularRing(row) {
    if (row.padDiameter === null || row.padDiameter === undefined ||
        row.viaDiameter === null || row.viaDiameter === undefined ||
        row.sc === null || row.sc === undefined) return null;
    return row.padDiameter / 2 - row.viaDiameter / 2 - row.sc;
  }

  /* ---------------- units + basic stats (M4) ---------------- */

  function toUm(mm) { return mm * 1000; }

  function mean(xs) {
    if (!xs.length) return NaN;
    return xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
  }

  /** Sample standard deviation (ddof=1, like pandas); NaN when n < 2. */
  function std(xs) {
    if (xs.length < 2) return NaN;
    var m = mean(xs);
    var v = xs.reduce(function (a, b) { return a + (b - m) * (b - m); }, 0) / (xs.length - 1);
    return Math.sqrt(v);
  }

  /* ---------------- tolerance zones (M4) ---------------- */

  function getRings(settings) {
    var cfg = (settings && settings.VTP_REGISTRATION) || {};
    function num(v, fallback) {
      var n = parseFloat(v);
      return isNaN(n) ? fallback : n;
    }
    return {
      exceptional: num(cfg.ring_exceptional_um, 2.5),
      excellent: num(cfg.ring_excellent_um, 5.0),
      good: num(cfg.ring_good_um, 7.5),
      acceptable: num(cfg.ring_acceptable_um, 10.0)
    };
  }

  function zoneOf(scUm, rings) {
    if (scUm <= rings.exceptional) return 'exceptional';
    if (scUm <= rings.excellent) return 'excellent';
    if (scUm <= rings.good) return 'good';
    if (scUm <= rings.acceptable) return 'acceptable';
    return 'fail';
  }

  /* ---------------- QC tile combiner (M4) ---------------- */

  /**
   * Annular-ring summary over rows (rings in mm, threshold in µm).
   * Null when no usable ring — the caller skips the tiles, like Python.
   */
  function annularStats(rows, thresholdUm) {
    var vals = [];
    (rows || []).forEach(function (r) {
      if (r.annularRing !== null && r.annularRing !== undefined && !isNaN(r.annularRing))
        vals.push({ um: r.annularRing * 1000, row: r });
    });
    if (!vals.length) return null;
    var ums = vals.map(function (v) { return v.um; });
    var worst = vals.reduce(function (a, b) { return b.um < a.um ? b : a; });
    var fails = ums.filter(function (v) { return v < thresholdUm; }).length;
    return {
      n: vals.length,
      min: Math.min.apply(null, ums),
      max: Math.max.apply(null, ums),
      mean: mean(ums),
      std: std(ums),
      failCount: fails,
      failPct: fails / vals.length * 100,
      worst: { location: worst.row.location, gridId: worst.row.gridId, valueUm: worst.um }
    };
  }

  /* ---------------- distance shrinkage (M4) ---------------- */

  var QUADRANTS = ['UL', 'LL', 'LR', 'UR'];
  var CORNER_IDX = { TL: '1', TR: '4', BL: '2', BR: '3' };

  function locOf(quad, corner) { return quad + '_' + CORNER_IDX[corner]; }

  function quadLengths(locMap, quad) {
    var need = ['TL', 'TR', 'BL', 'BR'].map(function (c) { return locOf(quad, c); });
    for (var i = 0; i < need.length; i++) if (!locMap[need[i]]) return null;
    var tl = locMap[need[0]], tr = locMap[need[1]],
        bl = locMap[need[2]], br = locMap[need[3]];
    return { xLen: (Math.abs(tr.x - tl.x) + Math.abs(br.x - bl.x)) / 2,
             yLen: (Math.abs(tl.y - bl.y) + Math.abs(tr.y - br.y)) / 2 };
  }

  /**
   * Distance-only shrinkage per quadrant + full-panel + uniformity + outliers.
   * Port of Python compute_distance_shrinkage. nominalCoords: {LOC: {x, y}} in
   * the same units as row coordX/coordY. Returns {quadrant, fullPanel,
   * uniformity, outliers, warnings}.
   */
  function qpShrinkage(rows, nominalCoords, outlierPpm) {
    if (outlierPpm === undefined) outlierPpm = 50;
    var warnings = [];
    rows = rows || [];
    if (!rows.length) return { quadrant: [], fullPanel: null, uniformity: null, outliers: [], warnings: ['No measured rows in scope.'] };

    var measured = {};
    rows.forEach(function (r) {
      if (r.location && r.coordX !== null && r.coordX !== undefined &&
          r.coordY !== null && r.coordY !== undefined && !measured[r.location])
        measured[r.location] = { x: r.coordX, y: r.coordY };
    });

    var qRows = [];
    QUADRANTS.forEach(function (quad) {
      var n = quadLengths(nominalCoords || {}, quad);
      var m = quadLengths(measured, quad);
      if (!n || !m) { warnings.push('Missing required corner point(s) for quadrant ' + quad + '; skipped.'); return; }
      if (n.xLen === 0 || n.yLen === 0) { warnings.push('Quadrant ' + quad + ' has zero nominal pitch; skipped.'); return; }
      var dxMm = m.xLen - n.xLen, dyMm = m.yLen - n.yLen;
      qRows.push({
        quadrant: quad,
        xNominalMm: n.xLen, xMeasuredMm: m.xLen, deltaXUm: dxMm * 1000,
        xPct: dxMm / n.xLen * 100, xPpm: dxMm / n.xLen * 1000000,
        yNominalMm: n.yLen, yMeasuredMm: m.yLen, deltaYUm: dyMm * 1000,
        yPct: dyMm / n.yLen * 100, yPpm: dyMm / n.yLen * 1000000
      });
    });
    if (!qRows.length)
      return { quadrant: [], fullPanel: null, uniformity: null, outliers: [],
               warnings: warnings.length ? warnings : ['No shrinkage rows could be computed.'] };

    function avg(f) { return mean(qRows.map(function (q) { return q[f]; })); }
    function range(f) {
      var vs = qRows.map(function (q) { return q[f]; });
      return Math.max.apply(null, vs) - Math.min.apply(null, vs);
    }
    var fp = { xPct: avg('xPct'), yPct: avg('yPct'), xPpm: avg('xPpm'), yPpm: avg('yPpm') };
    fp.offsetPct = fp.xPct - fp.yPct;
    fp.offsetPpm = fp.xPpm - fp.yPpm;
    var uni = { rangeXPct: range('xPct'), rangeYPct: range('yPct'),
                rangeX: range('xPpm'), rangeY: range('yPpm') };
    uni.distortion2d = Math.hypot(uni.rangeX, uni.rangeY);

    var outliers = qRows.filter(function (q) {
      return Math.abs(q.xPpm - fp.xPpm) > outlierPpm || Math.abs(q.yPpm - fp.yPpm) > outlierPpm;
    }).map(function (q) {
      return { quadrant: q.quadrant,
        devXPct: Math.abs(q.xPct - fp.xPct), devYPct: Math.abs(q.yPct - fp.yPct),
        devX: Math.abs(q.xPpm - fp.xPpm), devY: Math.abs(q.yPpm - fp.yPpm),
        alert: 'Deviation > ' + outlierPpm + ' PPM from FP' };
    });

    return { quadrant: qRows, fullPanel: fp, uniformity: uni, outliers: outliers, warnings: warnings };
  }

  return {
    SCHEMA_VERSION: SCHEMA_VERSION,
    annularRing: annularRing,
    toUm: toUm,
    mean: mean,
    std: std,
    getRings: getRings,
    zoneOf: zoneOf,
    annularStats: annularStats,
    qpShrinkage: qpShrinkage
  };
})();
