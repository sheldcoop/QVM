/**
 * sample-data/make-samples.js - dev only:  node sample-data/make-samples.js
 *
 * Regenerates the built-in .txt samples with a fixed seed (LCG), so the
 * outputs are byte-stable. Pad positions sit on the CAM nominal grid, so the
 * coordinate-first locator resolves every site without header hints.
 */
const fs = require('fs'), path = require('path');

function lcg(seed) {
  let s = seed >>> 0;
  return function () {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const NOM = {
  UL_1: [-222.700, 239.875], UL_2: [-222.700, 4.125], UL_3: [-22.050, 4.125], UL_4: [-22.050, 239.875],
  LL_1: [-222.700, -4.125], LL_2: [-222.700, -239.875], LL_3: [-22.050, -239.875], LL_4: [-22.050, -4.125],
  LR_1: [20.300, -4.125], LR_2: [20.300, -239.875], LR_3: [220.950, -239.875], LR_4: [220.950, -4.125],
  UR_1: [20.300, 239.875], UR_2: [20.300, 4.125], UR_3: [220.950, 4.125], UR_4: [220.950, 239.875]
};
const PAD_D = 0.308911, VIA_D = 0.016742;

function ptvBlock(loc, px, py, dx, dy, id) {
  const sc = Math.hypot(dx, dy);
  const f = v => v.toFixed(6).padStart(15, ' ');
  return 'Circle: Pad_XX(ID:' + id + ', From 180 Pts.)\n' +
    '     Coord. X =       ' + f(px) + '\n' +
    '     Coord. Y =       ' + f(py) + '\n' +
    '     Diameter =         ' + PAD_D + '\n' +
    'Circle: Via_XX(ID:' + (id + 1) + ', From 70 Pts.)\n' +
    '     Coord. X =       ' + f(px + dx) + '\n' +
    '     Coord. Y =       ' + f(py + dy) + '\n' +
    '     Diameter =         ' + VIA_D + '\n' +
    'Distance: PtV_XX(ID:' + (id + 2) + ') between Via_XX and Pad_XX\n' +
    '           SC =        ' + f(sc) + '\n' +
    '           DX =        ' + f(dx) + '\n' +
    '           DY =        ' + f(dy) + '\n';
}

function vtpBlock(loc, px, py, dx, dy, id) {
  const sc = Math.hypot(dx, dy);
  const f = v => v.toFixed(6).padStart(15, ' ');
  return 'Circle: Via_XX(ID:' + id + ', From 65 Pts.)\n' +
    '     Coord. X =       ' + f(px + dx) + '\n' +
    '     Coord. Y =       ' + f(py + dy) + '\n' +
    '     Diameter =         ' + VIA_D + '\n' +
    'Circle: Pad_XX(ID:' + (id + 1) + ', From 180 Pts.)\n' +
    '     Coord. X =       ' + f(px) + '\n' +
    '     Coord. Y =       ' + f(py) + '\n' +
    '     Diameter =         ' + PAD_D + '\n' +
    'Distance: VtP_XX(ID:' + (id + 2) + ') between Pad_XX(ID:' + (id + 1) + ') and Via_XX(ID:' + id + ')\n' +
    '           SC =        ' + f(sc) + '\n' +
    '           DX =        ' + f(dx) + '\n' +
    '           DY =        ' + f(dy) + '\n';
}

function main() {
  const dir = __dirname;
  const rnd = lcg(20260930);
  // Pad to Via: all 16 sites, small shifts; LR_3 is the deliberate fail.
  let id = 1, ptv = '';
  Object.keys(NOM).forEach(loc => {
    const bad = loc === 'LR_3';
    const dx = bad ? 0.009 : (rnd() - 0.5) * 0.008;
    const dy = bad ? 0.012 : (rnd() - 0.5) * 0.008;
    ptv += ptvBlock(loc, NOM[loc][0], NOM[loc][1], dx, dy, id) + '\n';
    id += 3;
  });
  fs.writeFileSync(path.join(dir, 'Post PFC_Pad to Via_Panel 20_F.txt'), ptv);
  // Via to Pad: one site per quadrant.
  let jd = 1, vtp = '';
  ['UL_2', 'LL_3', 'LR_1', 'UR_4'].forEach(loc => {
    const dx = (rnd() - 0.5) * 0.006, dy = (rnd() - 0.5) * 0.006;
    vtp += vtpBlock(loc, NOM[loc][0], NOM[loc][1], dx, dy, jd) + '\n';
    jd += 3;
  });
  fs.writeFileSync(path.join(dir, 'Post PFC_Via to Pad_Panel 20_F.txt'), vtp);
  console.log('samples written');
}

main();
