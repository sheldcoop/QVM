/**
 * QVM Dashboard - config.js
 *
 * Program settings: fixed per installation, not per person. Tolerances and
 * other analyst-tunable numbers live in Settings (localStorage) from M5;
 * only the storage keys and app identity live here.
 *
 * NEVER put passwords, API keys or tokens here.
 */
window.QVM = window.QVM || {};
window.QVM.config = Object.freeze({
  app_name: 'QVM Dashboard',
  version: '0.1.0-m1',

  time_zone: 'Europe/Vienna',   // OPEN_QUESTIONS Q1: confirm lab time zone

  // Browser storage names (per-PC preferences only; session data stays in memory).
  local_prefix: 'qvm.'
});
