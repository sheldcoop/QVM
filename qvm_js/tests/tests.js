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
