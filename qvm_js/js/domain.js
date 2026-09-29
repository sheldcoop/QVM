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

  return {
    SCHEMA_VERSION: SCHEMA_VERSION
  };
})();
