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

  /**
   * Linear-interpolation quantile (type-7, like numpy/R default).
   * xs must be sorted ascending. Null when empty.
   */
  function quantile(sortedXs, p) {
    var n = sortedXs.length;
    if (!n) return null;
    var h = (n - 1) * p, j = Math.floor(h), g = h - j;
    return sortedXs[j] + (g && j + 1 < n ? g * (sortedXs[j + 1] - sortedXs[j]) : 0);
  }

  /** Five-number summary with min/max whiskers (plotly default). Null when empty. */
  function boxStats(xs) {
    var s = (xs || []).filter(function (v) { return v !== null && v !== undefined && !isNaN(v); })
      .sort(function (a, b) { return a - b; });
    if (!s.length) return null;
    return { min: s[0], q1: quantile(s, 0.25), median: quantile(s, 0.5),
             q3: quantile(s, 0.75), max: s[s.length - 1], n: s.length };
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

  /* ---------------- small matrix helpers (M5, no numpy) ---------------- */

  function transpose(A) {
    return A[0].map(function (_, j) { return A.map(function (row) { return row[j]; }); });
  }

  function matMul(A, B) {
    return A.map(function (row) {
      return B[0].map(function (_, j) {
        return row.reduce(function (s, v, k) { return s + v * B[k][j]; }, 0);
      });
    });
  }

  function matVec(A, v) {
    return A.map(function (row) {
      return row.reduce(function (s, x, k) { return s + x * v[k]; }, 0);
    });
  }

  /** Gaussian elimination for 3x3 (normal equations). Null when singular. */
  function solve3(M, b) {
    var A = [M[0].concat([b[0]]), M[1].concat([b[1]]), M[2].concat([b[2]])];
    for (var c = 0; c < 3; c++) {
      var p = c;
      for (var r = c + 1; r < 3; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
      if (Math.abs(A[p][c]) < 1e-12) return null;
      var tmp = A[c]; A[c] = A[p]; A[p] = tmp;
      for (r = c + 1; r < 3; r++) {
        var f = A[r][c] / A[c][c];
        for (var k = c; k < 4; k++) A[r][k] -= f * A[c][k];
      }
    }
    var x = [0, 0, 0];
    for (var i = 2; i >= 0; i--) {
      var s = A[i][3];
      for (var j = i + 1; j < 3; j++) s -= A[i][j] * x[j];
      x[i] = s / A[i][i];
    }
    return x;
  }

  /* ---------------- affine geometry (M5) ---------------- */

  function toPpm(scale) { return (1 - scale) * 1000000; }

  /**
   * Least-squares affine fit nominal → measured, QR-style decomposed.
   * nomPts/measPts: [[x, y]] in the same units. Null when underdetermined.
   */
  function affineFit(nomPts, measPts) {
    var n = nomPts.length;
    if (n < 3) return null;
    var A = nomPts.map(function (p) { return [p[0], p[1], 1]; });
    var At = transpose(A), AtA = matMul(At, A);
    var bx = measPts.map(function (p) { return p[0]; });
    var by = measPts.map(function (p) { return p[1]; });
    var px = solve3(AtA, matVec(At, bx));
    var py = solve3(AtA, matVec(At, by));
    if (!px || !py) return null;
    var a = px[0], b = px[1], tx = px[2], c = py[0], d = py[1], ty = py[2];
    var Sx = Math.hypot(a, c);
    if (Sx < 1e-12) return null;
    var thetaDeg = Math.atan2(c, a) * 180 / Math.PI;
    var cosT = a / Sx, sinT = c / Sx;
    var b2 = cosT * b + sinT * d, d2 = -sinT * b + cosT * d;
    var Sy = d2, shearDeg = Math.atan2(b2, d2) * 180 / Math.PI;
    var res = measPts.map(function (p, i) {
      return [p[0] - (a * nomPts[i][0] + b * nomPts[i][1] + tx),
              p[1] - (c * nomPts[i][0] + d * nomPts[i][1] + ty)];
    });
    var dist = res.map(function (r) { return Math.hypot(r[0], r[1]); });
    return { tx: tx, ty: ty, thetaDeg: thetaDeg, Sx: Sx, Sy: Sy, shearDeg: shearDeg,
             M: [[a, b], [c, d]], t: [tx, ty], resXY: res, resDist: dist,
             resRms: Math.sqrt(mean(dist.map(function (v) { return v * v; }))) };
  }

  /** Best-fit rotation + translation only (Kabsch, no scale). */
  function rigidFit(nomPts, measPts) {
    function avg(pts, k) { return mean(pts.map(function (p) { return p[k]; })); }
    var nc = [avg(nomPts, 0), avg(nomPts, 1)], mc = [avg(measPts, 0), avg(measPts, 1)];
    var h00 = 0, h01 = 0, h10 = 0, h11 = 0;
    for (var i = 0; i < nomPts.length; i++) {
      var nx = nomPts[i][0] - nc[0], ny = nomPts[i][1] - nc[1];
      var mx = measPts[i][0] - mc[0], my = measPts[i][1] - mc[1];
      h00 += nx * mx; h01 += nx * my; h10 += ny * mx; h11 += ny * my;
    }
    // 2x2 SVD of H via eigendecomposition of H^T H.
    var a = h00 * h00 + h10 * h10, b = h00 * h01 + h10 * h11, d = h01 * h01 + h11 * h11;
    var tr = a + d, det = a * d - b * b;
    var disc = Math.sqrt(Math.max(tr * tr - 4 * det, 0));
    var l1 = (tr + disc) / 2, l2 = (tr - disc) / 2;
    function evec(lam) {
      var v = [b, lam - a];
      if (Math.hypot(v[0], v[1]) < 1e-15) v = [lam - d, b];
      if (Math.hypot(v[0], v[1]) < 1e-15) return [1, 0];
      var n2 = Math.hypot(v[0], v[1]);
      return [v[0] / n2, v[1] / n2];
    }
    var v1 = evec(l1), v2 = [-v1[1], v1[0]];
    function uOf(v, sig) {
      if (sig < 1e-12) return [-v[1], v[0]];
      var Hv = [h00 * v[0] + h01 * v[1], h10 * v[0] + h11 * v[1]];
      return [Hv[0] / sig, Hv[1] / sig];
    }
    var u1 = uOf(v1, Math.sqrt(Math.max(l1, 0))), u2 = uOf(v2, Math.sqrt(Math.max(l2, 0)));
    // R = V C U^T, C corrects a reflected fit back to a rotation.
    var detVU = (v1[0] * u1[0] + v2[0] * u2[0]) * (v1[1] * u1[1] + v2[1] * u2[1]) -
                (v1[0] * u1[1] + v2[0] * u2[1]) * (v1[1] * u1[0] + v2[1] * u2[0]);
    var sgn = detVU < 0 ? -1 : 1;
    var R = [[v1[0] * u1[0] + sgn * v2[0] * u2[0], v1[0] * u1[1] + sgn * v2[0] * u2[1]],
             [v1[1] * u1[0] + sgn * v2[1] * u2[0], v1[1] * u1[1] + sgn * v2[1] * u2[1]]];
    var t = [mc[0] - (R[0][0] * nc[0] + R[0][1] * nc[1]),
             mc[1] - (R[1][0] * nc[0] + R[1][1] * nc[1])];
    return { R: R, t: t };
  }

  function matchedDots(rows, nominal) {
    var nom = [], meas = [], locations = [], quadrants = [];
    (rows || []).forEach(function (r) {
      var n = (nominal || {})[r.location];
      if (!n || r.coordX === null || r.coordX === undefined ||
          r.coordY === null || r.coordY === undefined) return;
      nom.push([n.x, n.y]);
      meas.push([r.coordX, r.coordY]);
      locations.push(r.location);
      quadrants.push(String(r.location).split('_')[0]);
    });
    return { nom: nom, meas: meas, locations: locations, quadrants: quadrants };
  }

  function csCfg(settings) {
    var defaults = { outlier_um: 50, rotation_warn_deg: 0.3, aniso_ppm: 100, shrink_ppm: 50 };
    var out = {}, k;
    for (k in defaults) out[k] = defaults[k];
    var src = (settings && settings.CORE_SHRINKAGE) || {};
    for (k in defaults) {
      var v = parseFloat(src[k]);
      if (!isNaN(v)) out[k] = v;
    }
    return out;
  }

  function detectOutliers(nom, meas, outlierUm) {
    var n = nom.length;
    var inlier = [], removed = [], i;
    for (i = 0; i < n; i++) inlier.push(true);
    var fit = affineFit(nom, meas);
    while (inlier.filter(Boolean).length > 4) {
      var ni = [], mi = [];
      for (i = 0; i < n; i++) if (inlier[i]) { ni.push(nom[i]); mi.push(meas[i]); }
      fit = affineFit(ni, mi);
      if (!fit) break;
      var worst = -1, worstRes = -1;
      for (i = 0; i < n; i++) {
        if (!inlier[i]) continue;
        var px = fit.M[0][0] * nom[i][0] + fit.M[0][1] * nom[i][1] + fit.t[0];
        var py = fit.M[1][0] * nom[i][0] + fit.M[1][1] * nom[i][1] + fit.t[1];
        var res = Math.hypot(meas[i][0] - px, meas[i][1] - py) * 1000;
        if (res > worstRes) { worstRes = res; worst = i; }
      }
      if (worstRes > outlierUm) { inlier[worst] = false; removed.push(worst); }
      else break;
    }
    return { removed: removed, inlier: inlier, fit: fit };
  }

  function classifyDistortion(sxPpm, syPpm, maxResUm, cfg) {
    if (maxResUm > cfg.outlier_um) return 'Local distortion / outlier dot(s)';
    if (Math.abs(sxPpm - syPpm) > cfg.aniso_ppm) return 'Anisotropic shrinkage';
    if (Math.abs(sxPpm) > cfg.shrink_ppm || Math.abs(syPpm) > cfg.shrink_ppm)
      return 'Uniform shrinkage';
    return 'Stable';
  }

  /**
   * Single-pass geometry analysis for one layer. Returns null when fewer
   * than 4 fiducials match — every CS product derives from this.
   */
  function analyzeLayer(rows, nominal, settings) {
    var cfg = csCfg(settings);
    var m = matchedDots(rows, nominal);
    if (m.nom.length < 4) return null;
    var fit = affineFit(m.nom, m.meas);
    if (!fit) return null;
    var det = detectOutliers(m.nom, m.meas, cfg.outlier_um);
    var rig = rigidFit(m.nom, m.meas);
    return {
      nom: m.nom, meas: m.meas, locations: m.locations, quadrants: m.quadrants,
      cfg: cfg, fit: fit, fitRobust: det.fit,
      removed: det.removed, outliers: det.removed.map(function (i) { return m.locations[i]; }),
      rigidR: rig.R, rigidT: rig.t,
      center: [mean(m.nom.map(function (p) { return p[0]; })),
               mean(m.nom.map(function (p) { return p[1]; }))],
      nPoints: m.nom.length
    };
  }

  /** Headline shrinkage numbers for one layer (port of compute_shrinkage_summary). */
  function affineSummary(a) {
    if (!a) return null;
    var resMax = Math.max.apply(null, a.fit.resDist) * 1000;
    return {
      sxPpm: toPpm(a.fit.Sx), syPpm: toPpm(a.fit.Sy),
      sxPpmRobust: toPpm(a.fitRobust ? a.fitRobust.Sx : a.fit.Sx),
      syPpmRobust: toPpm(a.fitRobust ? a.fitRobust.Sy : a.fit.Sy),
      rotationDeg: a.fit.thetaDeg, shearDeg: a.fit.shearDeg,
      rmsUm: a.fit.resRms * 1000, maxUm: resMax,
      nOutliers: a.outliers.length, outliers: a.outliers, nPoints: a.nPoints,
      pattern: classifyDistortion(toPpm(a.fit.Sx), toPpm(a.fit.Sy), resMax, a.cfg)
    };
  }

  /** Per-dot residuals with outlier flags (the defect locator). */
  function residuals(a) {
    if (!a) return [];
    var out = new Set(a.outliers);
    return a.locations.map(function (loc, i) {
      return { location: loc, quadrant: a.quadrants[i],
        resXUm: a.fit.resXY[i][0] * 1000, resYUm: a.fit.resXY[i][1] * 1000,
        resDistUm: a.fit.resDist[i] * 1000, outlier: out.has(loc) };
    });
  }

  var QP_NOMINAL_X = 200.65, QP_NOMINAL_Y = 235.75;
  var QP_FORMULAS = {
    UL: [['X1', -1, 1, 4, 'x', QP_NOMINAL_X], ['X2', -1, 2, 3, 'x', QP_NOMINAL_X],
         ['Y1', 1, 1, 2, 'y', QP_NOMINAL_Y], ['Y2', 1, 4, 3, 'y', QP_NOMINAL_Y]],
    LL: [['X1', -1, 1, 4, 'x', QP_NOMINAL_X], ['X2', -1, 2, 3, 'x', QP_NOMINAL_X],
         ['Y1', -1, 2, 1, 'y', QP_NOMINAL_Y], ['Y2', -1, 3, 4, 'y', QP_NOMINAL_Y]],
    LR: [['X1', 1, 4, 1, 'x', QP_NOMINAL_X], ['X2', 1, 3, 2, 'x', QP_NOMINAL_X],
         ['Y1', -1, 2, 1, 'y', QP_NOMINAL_Y], ['Y2', -1, 3, 4, 'y', QP_NOMINAL_Y]],
    UR: [['X1', 1, 4, 1, 'x', QP_NOMINAL_X], ['X2', 1, 3, 2, 'x', QP_NOMINAL_X],
         ['Y1', 1, 1, 2, 'y', QP_NOMINAL_Y], ['Y2', 1, 4, 3, 'y', QP_NOMINAL_Y]]
  };

  /**
   * QP pitch error per quadrant in mm (negative = shrank). Missing dots
   * yield null cells. Port of compute_qp_shrinkage; rows carry coordX/coordY.
   */
  function qpitch(rows) {
    if (!rows || !rows.length) return [];
    var locMap = {};
    rows.forEach(function (r) { locMap[r.location] = r; });
    return QUADRANTS.map(function (quad) {
      var row = { quadrant: quad };
      QP_FORMULAS[quad].forEach(function (f) {
        var a = locMap[quad + '_' + f[2]], b = locMap[quad + '_' + f[3]];
        var va = a ? (f[4] === 'x' ? a.coordX : a.coordY) : null;
        var vb = b ? (f[4] === 'x' ? b.coordX : b.coordY) : null;
        row[f[0].toLowerCase()] = (va === null || va === undefined || vb === null || vb === undefined)
          ? null : f[1] * (va - vb) - f[5];
      });
      return row;
    });
  }

  /** X/Y scale + shrinkage ppm per quadrant plus Overall. */
  function scaleFactor(rows) {
    var qp = qpitch(rows);
    if (!qp.length) return [];
    function sc(v, nom) { return (v === null || v === undefined) ? null : (v + nom) / nom; }
    function avg2(a, b) {
      if (a === null && b === null) return null;
      if (a === null) return b;
      if (b === null) return a;
      return (a + b) / 2;
    }
    var out = qp.map(function (q) {
      var xs = avg2(sc(q.x1, QP_NOMINAL_X), sc(q.x2, QP_NOMINAL_X));
      var ys = avg2(sc(q.y1, QP_NOMINAL_Y), sc(q.y2, QP_NOMINAL_Y));
      return { quadrant: q.quadrant, xScale: xs, yScale: ys,
               xPpm: xs === null ? null : (1 - xs) * 1000000,
               yPpm: ys === null ? null : (1 - ys) * 1000000 };
    });
    function avgF(f) {
      var vs = out.map(function (q) { return q[f]; }).filter(function (v) { return v !== null; });
      return vs.length ? mean(vs) : null;
    }
    var ox = avgF('xScale'), oy = avgF('yScale');
    out.push({ quadrant: 'Overall', xScale: ox, yScale: oy,
               xPpm: ox === null ? null : (1 - ox) * 1000000,
               yPpm: oy === null ? null : (1 - oy) * 1000000 });
    return out;
  }

  /**
   * Per-dot Front − Back difference in µm (nominal cancels: same CAM).
   * Rows need location/quadrant/gridId/coordX/coordY.
   */
  function frontBack(frontRows, backRows) {
    if (!frontRows || !frontRows.length || !backRows || !backRows.length) return [];
    var back = {};
    backRows.forEach(function (r) { back[r.location] = r; });
    var out = [];
    frontRows.forEach(function (f) {
      var b = back[f.location];
      if (!b || f.coordX === null || f.coordX === undefined) return;
      var dx = (f.coordX - b.coordX) * 1000, dy = (f.coordY - b.coordY) * 1000;
      out.push({ location: f.location, quadrant: String(f.location).split('_')[0],
                 gridId: f.gridId !== undefined ? f.gridId : null,
                 dxUm: dx, dyUm: dy, distUm: Math.hypot(dx, dy) });
    });
    return out;
  }

  function classifyVector(dx, dy, px, py, center, stableUm) {
    if (stableUm === undefined) stableUm = 3.0;
    var mag = Math.hypot(dx, dy);
    if (mag < stableUm) return 'stable';
    var rx = px - center[0], ry = py - center[1];
    var rn = Math.hypot(rx, ry);
    if (rn < 1e-9) return 'stable';
    var radial = dx * (rx / rn) + dy * (ry / rn);
    var tang = dx * (-ry / rn) + dy * (rx / rn);
    if (Math.abs(radial) >= Math.abs(tang)) return radial > 0 ? 'expansion' : 'contraction';
    return 'twist';
  }

  /**
   * Per-dot displacement field for the Distortion Map. field 'total' keeps
   * scale (expansion arrows); 'residual' isolates local warp. Outlier dots
   * are re-labelled 'outlier'. Null analysis → [].
   */
  function deviationField(rows, nominal, settings, field, analysis) {
    var a = analysis || analyzeLayer(rows, nominal, settings);
    if (!a) return [];
    function applyRigid(p) {
      return [a.rigidR[0][0] * p[0] + a.rigidR[0][1] * p[1] + a.rigidT[0],
              a.rigidR[1][0] * p[0] + a.rigidR[1][1] * p[1] + a.rigidT[1]];
    }
    var out = new Set(a.outliers);
    return a.locations.map(function (loc, i) {
      var dev = field === 'residual'
        ? a.fit.resXY[i]
        : [a.meas[i][0] - applyRigid(a.nom[i])[0], a.meas[i][1] - applyRigid(a.nom[i])[1]];
      var dxu = dev[0] * 1000, dyu = dev[1] * 1000;
      var klass = classifyVector(dxu, dyu, a.nom[i][0], a.nom[i][1], a.center);
      return { location: loc, quadrant: a.quadrants[i],
               nomX: a.nom[i][0], nomY: a.nom[i][1],
               devXUm: dxu, devYUm: dyu, magUm: Math.hypot(dxu, dyu),
               klass: out.has(loc) ? 'outlier' : klass, outlier: out.has(loc) };
    });
  }

  return {
    SCHEMA_VERSION: SCHEMA_VERSION,
    annularRing: annularRing,
    toUm: toUm,
    mean: mean,
    std: std,
    quantile: quantile,
    boxStats: boxStats,
    getRings: getRings,
    zoneOf: zoneOf,
    annularStats: annularStats,
    qpShrinkage: qpShrinkage,
    toPpm: toPpm,
    affineFit: affineFit,
    rigidFit: rigidFit,
    matchedDots: matchedDots,
    csCfg: csCfg,
    analyzeLayer: analyzeLayer,
    affineSummary: affineSummary,
    residuals: residuals,
    qpitch: qpitch,
    scaleFactor: scaleFactor,
    frontBack: frontBack,
    classifyVector: classifyVector,
    deviationField: deviationField
  };
})();
