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

  return {
    SCHEMA_VERSION: SCHEMA_VERSION,
    annularRing: annularRing
  };
})();
