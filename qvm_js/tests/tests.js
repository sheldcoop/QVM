/**
 * tests/tests.js - every domain rule, with a test.
 *
 * Runs in tests/test.html (open it in Edge or Chrome) and from the command
 * line (node tests/run-tests.js). Results land in window.QVM_TESTS:
 *   {groups: [{name, rows: [{ok, name, detail}]}], passed, failed, done (Promise)}
 * UI components are covered by tests/ui-smoke.js (fake DOM), not here.
 */
(function () {
  'use strict';

  var D = window.QVM.domain;
  var cfg = window.QVM.config;
  var TH = window.QVM.themes;

  /* ---------------- tiny test runner ---------------- */
  var T = window.QVM_TESTS = { groups: [], passed: 0, failed: 0, done: null };
  var current = null;

  function group(name) { current = { name: name, rows: [] }; T.groups.push(current); }

  function record(ok, name, detail) {
    if (ok) T.passed++; else T.failed++;
    current.rows.push({ ok: ok, name: name, detail: detail || '' });
  }

  function eq(name, actual, expected) {
    var a = JSON.stringify(actual), e = JSON.stringify(expected);
    record(a === e, name, a === e ? '' : 'expected ' + e + ', got ' + a);
  }

  function ok(name, cond, detail) { record(!!cond, name, cond ? '' : (detail || 'expected true')); }

  /* Four PtV blocks, one per quadrant: A(60,100) LL, B(450,100) LR,
     C(60,400) UL, D(450,400) UR. DX=0.003, DY=0.004, SC=0.005 consistent.
     Mode 'SC' corrupts the first block's SC to 0.5 to exercise repair. */
  function ptvSample(mode) {
    var pts = [[60, 100], [450, 100], [60, 400], [450, 400]];
    return pts.map(function (p, i) {
      var sc = (mode === 'SC' && i === 0) ? 0.5 : 0.005;
      return 'Circle: Pad_XX(ID:' + (i * 3 + 1) + ', From 180 Pts.)\n' +
        '     Coord. X =        ' + p[0] + '\n' +
        '     Coord. Y =       ' + p[1] + '\n' +
        '     Diameter =         0.308911\n' +
        'Circle: Via_XX(ID:' + (i * 3 + 2) + ', From 70 Pts.)\n' +
        '     Coord. X =        ' + (p[0] + 0.003) + '\n' +
        '     Coord. Y =       ' + (p[1] + 0.004) + '\n' +
        '     Diameter =         0.016742\n' +
        'Distance: PtV_XX(ID:' + (i * 3 + 3) + ') between Via_XX and Pad_XX\n' +
        '           SC =         ' + sc + '\n' +
        '           DX =         0.003\n' +
        '           DY =         0.004\n';
    }).join('\n');
  }

  /* One VtP block: via circle first with coords, pad diameter-only. */
  function vtpSample() {
    return 'Circle: Via_LL_2(ID:1, From 65 Pts.)\n' +
      '     Coord. X =        63.856611\n' +
      '     Coord. Y =       104.630820\n' +
      '     Diameter =         0.016742\n' +
      'Circle: Pad_LL_2(ID:2, From 180 Pts.)\n' +
      '     Diameter =         0.308911\n' +
      'Distance: VtP_LL_2(ID:3) between Pad_LL_2(ID:2) and Via_LL_2(ID:1)\n' +
      '           SC =         0.003728\n' +
      '           DX =         0.000592\n' +
      '           DY =         0.003681\n';
  }

  function run() {
    /* =============== config =============== */
    group('Config');
    eq('app name', cfg.app_name, 'QVM Dashboard');
    ok('local prefix', typeof cfg.local_prefix === 'string' && cfg.local_prefix.length > 0);
    ok('config frozen', Object.isFrozen(cfg));

    /* =============== domain =============== */
    group('Domain shell');
    eq('schema version starts at 1', D.SCHEMA_VERSION, 1);

    /* =============== filenames =============== */
    group('Filenames');
    var P = window.QVM.parse;
    eq('ptv hint + panel + side', P.parseFilename('Post PFC_Pad to Via_Panel 20_F.txt'),
      { formatHint: 'Pad to Via', panel: '20', side: 'F', buildUp: 'Unknown' });
    eq('vtp hint', P.parseFilename('Via to Pad_Panel 25_F.txt').formatHint, 'Via to Pad');
    eq('no hint', P.parseFilename('mystery.txt').formatHint, null);
    eq('BU token', P.parseFilename('x_BU-02_Panel 3_B.txt').buildUp, 'BU-02');

    /* =============== build-up normalisation =============== */
    group('Build Up');
    eq('bare number', P.normalizeBuildUp('2'), 'BU-02');
    eq('bu02', P.normalizeBuildUp('BU02'), 'BU-02');
    eq('unknown -> null', P.normalizeBuildUp('Unknown'), null);
    eq('custom kept', P.normalizeBuildUp('TOP-A'), 'TOP-A');

    /* =============== PtV parsing =============== */
    group('PtV content');
    var ptv = ptvSample();
    var r = P.parseQvmContent(ptv, undefined);
    eq('process', r.process, 'Pad to Via');
    eq('four rows', r.rows.length, 4);
    eq('locations by quadrant', r.rows.map(function (x) { return x.location; }),
      ['LL_1', 'LR_1', 'UL_1', 'UR_1']);
    eq('grid ids', r.rows.map(function (x) { return x.gridId; }), [21, 31, 11, 41]);
    ok('no warnings on clean input', r.warnings.length === 0);

    /* =============== VtP parsing =============== */
    group('VtP content');
    var v = P.parseQvmContent(vtpSample(), undefined);
    eq('process', v.process, 'Via to Pad');
    eq('pad coords optional', v.rows[0].coordX !== null, true);

    /* =============== SC repair =============== */
    group('SC normalisation');
    var bad = P.parseQvmContent(ptvSample('SC'), undefined);
    ok('mismatch repaired with warning',
      Math.abs(bad.rows[0].sc - 0.005) < 1e-12 && bad.warnings.length === 1);

    /* =============== annular ring =============== */
    group('Annular ring');
    ok('formula', Math.abs(D.annularRing(
      { padDiameter: 0.308911, viaDiameter: 0.016742, sc: 0.005 }) - 0.1410845) < 1e-6);
    eq('missing input -> null',
      D.annularRing({ padDiameter: 0.308911, viaDiameter: null, sc: 0.005 }), null);

    /* =============== ingest =============== */
    group('Ingest');
    var ing = P.ingestFile('Post PFC_Pad to Via_Panel 20_F.txt', ptvSample(), undefined, {});
    eq('rows carry panel/side', [ing.rows[0].panel, ing.rows[0].side], ['20', 'F']);
    eq('buildUp unknown', ing.rows[0].buildUp, 'Unknown');
    ok('annular ring attached', Math.abs(ing.rows[0].annularRing - 0.1410845) < 1e-6);
    ok('hint matches content: no warnings', ing.uiWarnings.length === 0);
    var ing2 = P.ingestFile('x.txt', ptvSample(), undefined,
      { process: 'Via to Pad', panel: '9', side: 'B', buildUp: '3' });
    eq('overrides win', [ing2.rows[0].process, ing2.rows[0].panel, ing2.rows[0].side, ing2.rows[0].buildUp],
      ['Via to Pad', '9', 'B', 'BU-03']);
    ok('override warnings', ing2.uiWarnings.length === 1);
    var ing3 = P.ingestFile('mystery.txt', ptvSample(), undefined, {});
    ok('no-hint warning', ing3.uiWarnings.length === 1);

    /* =============== stats primitives =============== */
    group('Stats primitives');
    eq('toUm', D.toUm(0.005), 5);
    eq('mean', D.mean([2, 4, 4, 4, 5, 5, 7, 9]), 5);
    ok('sample std ddof=1', Math.abs(D.std([2, 4, 4, 4, 5, 5, 7, 9]) - 2.1380899352994695) < 1e-9);
    ok('std needs n>=2', isNaN(D.std([3])) && isNaN(D.std([])));

    /* =============== zones =============== */
    group('Zones');
    var rings = D.getRings(undefined);
    eq('default rings', rings, { exceptional: 2.5, excellent: 5.0, good: 7.5, acceptable: 10.0 });
    eq('custom rings', D.getRings({ VTP_REGISTRATION: { ring_acceptable_um: 12 } }).acceptable, 12);
    eq('zone boundaries',
      [2.5, 5, 7.5, 10, 10.1].map(function (v) { return D.zoneOf(v, rings); }),
      ['exceptional', 'excellent', 'good', 'acceptable', 'fail']);

    /* =============== QC combiner =============== */
    group('QC combiner');
    var qrows = [
      { location: 'UL_1', gridId: 11, annularRing: 0.14 },
      { location: 'UL_2', gridId: 12, annularRing: 0.10 },
      { location: 'UL_3', gridId: 13, annularRing: null }
    ];
    var st = D.annularStats(qrows, 120);
    ok('min/max', Math.abs(st.min - 100) < 1e-9 && Math.abs(st.max - 140) < 1e-9);
    eq('fails', [st.failCount, st.failPct, st.n], [1, 50, 2]);
    eq('worst site', [st.worst.location, st.worst.gridId], ['UL_2', 12]);
    eq('empty -> null', D.annularStats([], 120), null);
    eq('all null -> null', D.annularStats([{ annularRing: null }], 120), null);

    /* =============== QP shrinkage =============== */
    group('QP shrinkage');
    var nom = {
      UL_1: { x: -200, y: 200 }, UL_4: { x: 0, y: 200 },
      UL_2: { x: -200, y: 0 }, UL_3: { x: 0, y: 0 },
      LL_1: { x: -200, y: 0 }, LL_4: { x: 0, y: 0 },
      LL_2: { x: -200, y: -200 }, LL_3: { x: 0, y: -200 },
      LR_1: { x: 0, y: 0 }, LR_4: { x: 200, y: 0 },
      LR_2: { x: 0, y: -200 }, LR_3: { x: 200, y: -200 },
      UR_1: { x: 0, y: 200 }, UR_4: { x: 200, y: 200 },
      UR_2: { x: 0, y: 0 }, UR_3: { x: 200, y: 0 }
    };
    var mrows = Object.keys(nom).map(function (loc) {
      return { location: loc, coordX: nom[loc].x + (loc === 'UL_3' ? 0.2 : 0),
               coordY: nom[loc].y };
    });
    var shr = D.qpShrinkage(mrows, nom, 200);
    eq('four quadrants', shr.quadrant.length, 4);
    var ul = shr.quadrant.filter(function (q) { return q.quadrant === 'UL'; })[0];
    function near(a, b) { return Math.abs(a - b) < 1e-6; }
    ok('UL x ppm', near(ul.xPpm, 500));
    ok('FP x ppm', near(shr.fullPanel.xPpm, 125));
    eq('FP y ppm', shr.fullPanel.yPpm, 0);
    ok('QTQ x', near(shr.uniformity.rangeX, 500));
    ok('2d distortion', near(shr.uniformity.distortion2d, 500));
    eq('one outlier', shr.outliers.map(function (o) { return o.quadrant; }), ['UL']);
    eq('no warnings', shr.warnings.length, 0);
    eq('empty rows', D.qpShrinkage([], nom).warnings,
      ['No measured rows in scope.']);

    /* =============== affine fit =============== */
    group('Affine fit');
    function xform(pts, s, deg, tx, ty) {
      var r = deg * Math.PI / 180, c = Math.cos(r), s2 = Math.sin(r);
      return pts.map(function (p) {
        return [s * (c * p[0] - s2 * p[1]) + tx, s * (s2 * p[0] + c * p[1]) + ty];
      });
    }
    var sq = [[-100, -100], [100, -100], [100, 100], [-100, 100]];
    var af = D.affineFit(sq, xform(sq, 0.9999, 0.1, 2, -1));
    function near(a, b, t) { return Math.abs(a - b) < (t || 1e-6); }
    ok('scale recovered', near(af.Sx, 0.9999, 1e-9) && near(af.Sy, 0.9999, 1e-9));
    ok('rotation recovered', near(af.thetaDeg, 0.1, 1e-9));
    ok('translation recovered', near(af.tx, 2, 1e-9) && near(af.ty, -1, 1e-9));
    ok('tight fit, ~0 residual', af.resRms < 1e-9);
    eq('underdetermined -> null', D.affineFit(sq.slice(0, 2), sq.slice(0, 2)), null);

    /* =============== rigid fit =============== */
    group('Rigid fit');
    var rg = D.rigidFit(sq, xform(sq, 1, 5, 3, -2));
    var R = rg.R;
    ok('orthonormal det +1',
      near(R[0][0] * R[0][0] + R[1][0] * R[1][0], 1, 1e-9) &&
      near(R[0][0] * R[1][0] + R[0][1] * R[1][1], 0, 1e-9) &&
      near(R[0][0] * R[1][1] - R[0][1] * R[1][0], 1, 1e-9));
    ok('angle recovered', near(Math.atan2(R[1][0], R[0][0]) * 180 / Math.PI, 5, 1e-9));
    ok('translation recovered', near(rg.t[0], 3, 1e-9) && near(rg.t[1], -2, 1e-9));

    /* =============== layer analysis =============== */
    group('Layer analysis');
    function csRows(scale, badLoc) {
      // Eight dots: with only six the one bad dot smears the fit enough to
      // take a neighbour with it (same in Python) — eight isolates it exactly.
      var locs = ['UL_1', 'UL_2', 'UL_3', 'UL_4', 'LL_1', 'LL_2', 'LL_3', 'LL_4'];
      var base = { UL_1: [-200, 200], UL_2: [-200, 0], UL_3: [0, 0], UL_4: [0, 200],
                   LL_1: [-200, 0], LL_2: [-200, -200], LL_3: [0, -200], LL_4: [0, 0] };
      return locs.map(function (loc) {
        var dx = loc === badLoc ? 1 : 0;
        return { location: loc, coordX: base[loc][0] * scale + dx, coordY: base[loc][1] * scale };
      });
    }
    function csNom() {
      return { UL_1: { x: -200, y: 200 }, UL_2: { x: -200, y: 0 }, UL_3: { x: 0, y: 0 },
               UL_4: { x: 0, y: 200 }, LL_1: { x: -200, y: 0 }, LL_2: { x: -200, y: -200 },
               LL_3: { x: 0, y: -200 }, LL_4: { x: 0, y: 0 } };
    }
    eq('fewer than 4 -> null', D.analyzeLayer(csRows(1).slice(0, 3), csNom()), null);
    var stable = D.affineSummary(D.analyzeLayer(csRows(1), csNom()));
    eq('identical -> Stable', stable.pattern, 'Stable');
    var shrunk = D.affineSummary(D.analyzeLayer(csRows(0.9999), csNom()));
    eq('uniform shrink flagged', shrunk.pattern, 'Uniform shrinkage');
    ok('100 ppm detected', near(shrunk.sxPpm, 100, 1) && near(shrunk.syPpm, 100, 1));
    var bad = D.analyzeLayer(csRows(1, 'UL_3'), csNom());
    eq('bad dot isolated', bad.outliers, ['UL_3']);
    var res = D.residuals(bad);
    eq('residual flags', res.filter(function (r) { return r.outlier; })
      .map(function (r) { return r.location; }), ['UL_3']);

    /* =============== QP pitch + scale =============== */
    group('QP pitch');
    function qpRows(shift) {
      function L(loc, x, y) { return { location: loc, coordX: x, coordY: y }; }
      return [L('UL_1', 0, 235.75), L('UL_4', 200.65, 235.75),
              L('UL_2', 0, 0), L('UL_3', 200.65 + shift, 0),
              L('LL_1', 0, 0), L('LL_4', 200.65, 0),
              L('LL_2', 0, -235.75), L('LL_3', 200.65, -235.75),
              L('LR_1', 0, 0), L('LR_4', 200.65, 0),
              L('LR_2', 0, -235.75), L('LR_3', 200.65, -235.75),
              L('UR_1', 0, 235.75), L('UR_4', 200.65, 235.75),
              L('UR_2', 0, 0), L('UR_3', 200.65, 0)];
    }
    var qp0 = D.qpitch(qpRows(0)).filter(function (q) { return q.quadrant === 'UL'; })[0];
    ok('design pitch -> zeros',
      near(qp0.x1, 0, 1e-9) && near(qp0.x2, 0, 1e-9) &&
      near(qp0.y1, 0, 1e-9) && near(qp0.y2, 0, 1e-9));
    var qp1 = D.qpitch(qpRows(0.2)).filter(function (q) { return q.quadrant === 'UL'; })[0];
    ok('shifted pitch', near(qp1.x2, 0.2, 1e-9) && near(qp1.x1, 0, 1e-9));
    var sf = D.scaleFactor(qpRows(0.2));
    eq('overall row', sf.length, 5);
    var sful = sf.filter(function (q) { return q.quadrant === 'UL'; })[0];
    ok('expansion negative ppm', near(sful.xPpm, -498.4, 0.5));

    /* =============== front-back + field =============== */
    group('Front-back');
    var fb = D.frontBack(
      [{ location: 'UL_1', gridId: 11, coordX: 10, coordY: 20 }],
      [{ location: 'UL_1', gridId: 11, coordX: 10.01, coordY: 20.02 }]);
    ok('offsets', near(fb[0].dxUm, -10, 1e-9) && near(fb[0].distUm, Math.sqrt(500), 1e-9));
    eq('empty side -> []', D.frontBack([], [{ location: 'UL_1' }]), []);

    group('Deviation field');
    eq('too few -> []', D.deviationField(csRows(1).slice(0, 2), csNom()), []);
    var fld = D.deviationField(csRows(1), csNom(), undefined, 'total');
    ok('identical -> stable zeros',
      fld.every(function (d) { return d.magUm < 1e-9 && d.klass === 'stable'; }));
    eq('outward -> expansion', D.classifyVector(10, 0, 100, 0, [0, 0]), 'expansion');
    eq('tangential -> twist', D.classifyVector(0, 10, 100, 0, [0, 0]), 'twist');
    eq('tiny -> stable', D.classifyVector(1, 1, 100, 0, [0, 0]), 'stable');

    /* =============== box stats =============== */
    group('Box stats');
    eq('quantile type-7', [D.quantile([1, 2, 3, 4, 5], 0.25), D.quantile([1, 2, 3, 4, 5], 0.5),
      D.quantile([1, 2, 3, 4, 5], 0.75)], [2, 3, 4]);
    eq('quantile empty', D.quantile([], 0.5), null);
    eq('five-number', D.boxStats([5, 1, 3, 2, 4, null]),
      { min: 1, q1: 2, median: 3, q3: 4, max: 5, n: 5 });
    eq('boxStats empty', D.boxStats([]), null);

    /* =============== chart builders =============== */
    group('Chart builders');
    var stubTheme = { color: function (n) { return 'c:' + n; },
                      alpha: function (n, a) { return 'a:' + n + ':' + a; } };
    var C = window.QVM.charts;
    var grows = P.parseQvmContent(ptvSample(), undefined).rows;
    var grings = D.getRings(undefined);
    var bull = C.bullseyeBuild(grows, grings)(stubTheme);
    var p0 = bull.data.datasets[0].data[0];
    eq('bullseye points', bull.data.datasets[0].data.length, 4);
    ok('bullseye µm', Math.abs(p0.x - 3) < 1e-9 && Math.abs(p0.y - 4) < 1e-9);
    eq('bullseye zone color',
      bull.data.datasets[0].backgroundColor[0],
      'c:' + C.ZONE_TOKENS[D.zoneOf(grows[0].sc * 1000, grings)]);
    eq('bullseye rings', bull.options.plugins.qvmRings.rings, [2.5, 5, 7.5, 10]);
    eq('bullseye plugin wired', bull.plugins, [C.ringsPlugin]);
    ok('bullseye square aspect', bull.options.aspectRatio === 1);
    var bars = C.siteBarsBuild(grows, grings)(stubTheme);
    eq('bars sorted by grid', bars.data.labels, ['11', '21', '31', '41']);
    ok('bars carry values', bars.data.datasets[0].data.every(function (v) {
      return Math.abs(v - 5) < 1e-9;
    }));
    var box = C.boxBuild(grows)(stubTheme);
    eq('box quarters', box.data.labels, ['UL', 'LL', 'LR', 'UR']);
    eq('box datasets: range + 4 IQR + median', box.data.datasets.length, 6);
    eq('box IQR (single value per quarter here)', box.data.datasets[1].data[0], [5, 5]);
    eq('median points', box.data.datasets[5].data.length, 4);

    /* =============== quiver classifier =============== */
    group('Quiver classifier');
    var QC = { expansionThr: 0.5, twistDotThr: 0.2, twistMagUm: 10 };
    eq('outward', D.classifyQuiver(10, 0, 100, 0, 10, QC), 'Expansion');
    eq('inward', D.classifyQuiver(-10, 0, 100, 0, 10, QC), 'Contraction');
    eq('tangential', D.classifyQuiver(0, 20, 100, 0, 20, QC), 'Twist');
    eq('small tangential', D.classifyQuiver(0, 5, 100, 0, 5, QC), 'Offset');
    eq('zero shift', D.classifyQuiver(0, 0, 100, 0, 0, QC), 'Offset');

    /* =============== quiver builder =============== */
    group('Quiver builder');
    var qrows = P.parseQvmContent(ptvSample(), undefined).rows;
    var qcfg = C.quiverBuild(qrows, window.QVM.defaults.DEFAULT_SETTINGS, 100)(stubTheme);
    eq('four arrows', qcfg.options.plugins.qvmQuiver.arrows.length, 4);
    eq('pattern counts', qcfg.options.plugins.qvmQuiver.counts,
      { Expansion: 1, Contraction: 1, Twist: 0, Offset: 2 });
    eq('legend entries', qcfg.options.plugins.qvmQuiver.legend.length, 4);
    eq('plugin wired', qcfg.plugins, [C.quiverPlugin]);
    eq('panel axes', [qcfg.options.scales.x.min, qcfg.options.scales.x.max,
      qcfg.options.scales.y.min, qcfg.options.scales.y.max], [0.5, 4.5, 0.5, 4.5]);
    ok('arrow scaled by multiplier',
      qcfg.options.plugins.qvmQuiver.arrows[0].dx !== 0);

    /* =============== workbook =============== */
    group('Workbook');
    var E = window.QVM.export;
    var wbRows = P.parseQvmContent(ptvSample(), undefined).rows;
    var wb = E.buildQvmWorkbook({
      vtpRows: [], ptvRows: wbRows, vtpUslUm: 10, ptvUslUm: 10,
      rings: D.getRings(undefined), settings: window.QVM.defaults.DEFAULT_SETTINGS,
      meta: { date: '2026-09-30', files: ['s.txt'] },
      warnings: [{ file: 's.txt', text: 'w1' }], D: D
    });
    eq('sheet names', wb.SheetNames,
      ['Via to Pad', 'Pad to Via', 'Report', 'Analytics VTP', 'Analytics PTV',
       'Shrinkage Summary', 'Warnings']);
    var rep = XLSX.utils.sheet_to_json(wb.Sheets.Report, { header: 1 });
    ok('report meta + header',
      rep[0][0] === 'QVM Dashboard export' && rep[3][0] === 'Process');
    eq('report rows', rep.length, 4 + 4);
    var warn = XLSX.utils.sheet_to_json(wb.Sheets.Warnings, { header: 1 });
    eq('warnings sheet', warn[1], ['s.txt', 'w1']);

    /* =============== CS files =============== */
    group('CS content');
    eq('cs filename', P.parseCsFilename('Core_Shrinkage_Panel 20_Front.txt'),
      { isCoreShrinkage: true, panel: '20', layer: 'Front' });
    eq('non-cs filename', P.parseCsFilename('Post PFC_Pad to Via_Panel 20_F.txt').isCoreShrinkage, false);
    var csText = 'Circle: Pad_UL_1(ID:1, From 180 Pts.)\n' +
      '     Coord. X =        -222.700\n' +
      '     Coord. Y =       239.875\n' +
      '     Diameter =         0.3\n' +
      'Circle: LL_2(ID:2, From 170 Pts.)\n' +
      '     Coord. X =        -222.700\n' +
      '     Coord. Y =       -239.875\n' +
      '     Diameter =         0.3\n';
    var cs = P.parseCsContent(csText, 'Front', undefined);
    eq('two dots', cs.rows.length, 2);
    eq('first dot', [cs.rows[0].location, cs.rows[0].quadrant, cs.rows[0].gridId, cs.rows[0].layer],
      ['UL_1', 'UL', 11, 'Front']);
    eq('pad prefix tolerated', cs.rows[1 - 1].pointNum, 1);
    eq('garbage -> warning', P.parseCsContent('nothing here', 'Front', undefined).warning,
      'No circles parsed from Front layer.');
    var csi = P.ingestCsFile('Core_Shrinkage_Panel 20_Front.txt', csText, undefined, {});
    eq('cs ingest tags', [csi.rows[0].panel, csi.rows[0].layer, csi.rows[0].process],
      ['20', 'Front', 'Core Shrinkage']);
    eq('cs ingest quiet', csi.uiWarnings.length, 0);
    var csi2 = P.ingestCsFile('cs.txt', csText, undefined, { layer: 'Back', buildUp: '1' });
    eq('cs overrides', [csi2.rows[0].layer, csi2.rows[0].buildUp], ['Back', 'BU-01']);

    /* =============== session =============== */
    group('Session');
    var SE = window.QVM.session;
    SE.clear();
    SE.setScope({ panel: 'All', side: 'Both', buildUp: 'All', layer: 'Both' });
    SE.addFile({ name: 'a.txt', kind: 'qvm', rows: [
      { process: 'Pad to Via', panel: '20', side: 'F', buildUp: 'BU-01' },
      { process: 'Pad to Via', panel: '25', side: 'B', buildUp: 'Unknown' }
    ], parseWarnings: ['pw'], uiWarnings: [] });
    eq('rows by process', SE.rowsByProcess('Pad to Via').length, 2);
    eq('warnings carry file', SE.warnings(), [{ file: 'a.txt', text: 'pw' }]);
    eq('panels sorted', SE.panels(SE.allRows()), ['20', '25']);
    SE.setScope({ panel: '20' });
    eq('panel filter', SE.applyScope(SE.allRows(), { col: 'side', value: 'Both' }).length, 1);
    SE.setScope({ panel: 'All', side: 'F' });
    eq('side filter', SE.applyScope(SE.allRows(), { col: 'side', value: 'F' }).length, 1);
    var bu = SE.buStates(SE.allRows());
    eq('bu states', [bu.values, bu.hasUnknown], [['BU-01'], true]);
    eq('bu filter', SE.applyBu(SE.allRows(), 'BU-01').length, 1);
    eq('bu unknown', SE.applyBu(SE.allRows(), 'Unknown').length, 1);
    SE.removeFile('a.txt');
    eq('remove empties', SE.allRows().length, 0);
    SE.setScope({ panel: 'All', side: 'Both', buildUp: 'All', layer: 'Both' });

    /* =============== settings store =============== */
    group('Settings store');
    var S = window.QVM.settings;
    S.reset();
    eq('defaults live', S.get().VTP_REGISTRATION.ring_acceptable_um, 10);
    S.set({ VTP_REGISTRATION: { ring_acceptable_um: 12 } });
    eq('patch sticks', S.get().VTP_REGISTRATION.ring_acceptable_um, 12);
    eq('untouched keys survive', S.get().VTP_REGISTRATION.ring_good_um, 7.5);
    S.reset();
    eq('reset restores', S.get().VTP_REGISTRATION.ring_acceptable_um, 10);
    ok('rings follow settings', D.getRings(S.get()).acceptable === 10);

    /* =============== cs config =============== */
    group('CS config');
    eq('defaults', D.csCfg(undefined),
      { outlier_um: 50, rotation_warn_deg: 0.3, aniso_ppm: 100, shrink_ppm: 50 });
    eq('override', D.csCfg({ CORE_SHRINKAGE: { outlier_um: 30 } }).outlier_um, 30);

    /* =============== themes =============== */
    group('Themes');
    ok('theme list non-empty', TH.list.length > 0);
    ok('default theme exists', !!TH.byKey(TH.DEFAULT));
    ok('unknown key falls back to default', TH.byKey('no-such-theme') === null);
    ok('attrs carry scheme, never rely on name',
      TH.list.every(function (t) { var a = TH.attrs(t.key); return !!a['data-scheme']; }));
    ok('every theme has tokens', TH.list.every(function (t) {
      var v = TH.tokens(t); return v && v.bg && v.fg && v.surface;
    }));

    T.done = Promise.resolve();
  }

  run();
})();
