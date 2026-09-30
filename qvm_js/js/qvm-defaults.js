/**
 * QVM Dashboard - qvm-defaults.js
 *
 * Built-in defaults mirroring qvm_dashboard/config/settings.yaml (the Python
 * app). Analyst overrides land in Settings/localStorage in M5; until then
 * every consumer takes these. Column names are display labels for M6+;
 * parsed rows use stable internal keys (DECISIONS D6).
 */
window.QVM = window.QVM || {};
window.QVM.defaults = (function () {
  'use strict';

  var COLUMN_NAMES = {
    outer_diameter: 'Pad Diameter',
    inner_diameter: 'Via Parameter',
    x_distance: 'Shift (DX)',
    y_distance: 'Shift (DY)',
    ptv_distance: 'PtV Distance',
    annular_ring: 'Annular Ring',
    location: 'Location',
    grid_id: 'Grid ID',
    coord_x: 'Coord. X',
    coord_y: 'Coord. Y',
    total_shift: 'VtP Distance (SC)',
    item_type: 'Type',
    via_pts: 'Via Pts.',
    pad_pts: 'Pad Pts.'
  };

  var GRID_MAPPING = {
    UL_1: 11, UL_2: 12, UL_3: 13, UL_4: 14,
    LL_1: 21, LL_2: 22, LL_3: 23, LL_4: 24,
    LR_1: 31, LR_2: 32, LR_3: 33, LR_4: 34,
    UR_1: 41, UR_2: 42, UR_3: 43, UR_4: 44
  };

  var VTP_REGISTRATION = {
    ring_exceptional_um: 2.5,
    ring_excellent_um: 5.0,
    ring_good_um: 7.5,
    ring_acceptable_um: 10.0,
    vtp_usl_um: 10.0,
    outlier_cap_um: 1000.0,
    sc_override_enabled: true,
    sc_override_abs_error_um: 100.0,
    sc_override_rel_error_pct: 10.0
  };

  var PTV_REGISTRATION = {
    ptv_usl_um: 10.0,
    outlier_cap_um: 1000.0,
    sc_override_enabled: true,
    sc_override_abs_error_um: 100.0,
    sc_override_rel_error_pct: 10.0
  };

  var DIAGNOSTICS = {
    panel_center_x: 255.0,
    panel_center_y: 257.5
  };

  var DEFAULT_SETTINGS = {
    COLUMN_NAMES: COLUMN_NAMES,
    GRID_MAPPING: GRID_MAPPING,
    VTP_REGISTRATION: VTP_REGISTRATION,
    PTV_REGISTRATION: PTV_REGISTRATION,
    DIAGNOSTICS: DIAGNOSTICS
  };

  return {
    COLUMN_NAMES: COLUMN_NAMES,
    GRID_MAPPING: GRID_MAPPING,
    VTP_REGISTRATION: VTP_REGISTRATION,
    PTV_REGISTRATION: PTV_REGISTRATION,
    DIAGNOSTICS: DIAGNOSTICS,
    DEFAULT_SETTINGS: DEFAULT_SETTINGS
  };
})();
