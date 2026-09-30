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
    panel_center_y: 257.5,
    quiver_min_arrow_length: 0.05,
    quiver_expansion_dot_threshold: 0.5,
    quiver_twist_dot_threshold: 0.2,
    quiver_twist_magnitude_um: 10.0
  };

  var PLOT_SETTINGS = {
    vector_multiplier_default: 100
  };

  // Grid ID → panel plot position (col, row), 1-4. Mirrors theme.GRID_PLOT_POSITIONS.
  var GRID_PLOT_POSITIONS = {
    11: [1, 4], 12: [1, 3], 13: [2, 3], 14: [2, 4],
    21: [1, 2], 22: [1, 1], 23: [2, 1], 24: [2, 2],
    31: [3, 2], 32: [3, 1], 33: [4, 1], 34: [4, 2],
    41: [3, 4], 42: [3, 3], 43: [4, 3], 44: [4, 4]
  };

  var TOLERANCES = {
    annular_ring_min: 0.0
  };

  var CORE_SHRINKAGE = {
    outlier_um: 50.0,
    rotation_warn_deg: 0.30,
    aniso_ppm: 100.0,
    shrink_ppm: 50.0,
    shrink_usl_ppm: 1000.0
  };

  // CAM nominal fiducial coordinates (mm), shared by QP and CS analysis.
  var NOMINAL_COORDS = {
    UL_1: { x: -222.700, y: 239.875 }, UL_2: { x: -222.700, y: 4.125 },
    UL_3: { x: -22.050, y: 4.125 }, UL_4: { x: -22.050, y: 239.875 },
    LL_1: { x: -222.700, y: -4.125 }, LL_2: { x: -222.700, y: -239.875 },
    LL_3: { x: -22.050, y: -239.875 }, LL_4: { x: -22.050, y: -4.125 },
    LR_1: { x: 20.300, y: -4.125 }, LR_2: { x: 20.300, y: -239.875 },
    LR_3: { x: 220.950, y: -239.875 }, LR_4: { x: 220.950, y: -4.125 },
    UR_1: { x: 20.300, y: 239.875 }, UR_2: { x: 20.300, y: 4.125 },
    UR_3: { x: 220.950, y: 4.125 }, UR_4: { x: 220.950, y: 4.125 }
  };

  var DEFAULT_SETTINGS = {
    COLUMN_NAMES: COLUMN_NAMES,
    GRID_MAPPING: GRID_MAPPING,
    VTP_REGISTRATION: VTP_REGISTRATION,
    PTV_REGISTRATION: PTV_REGISTRATION,
    DIAGNOSTICS: DIAGNOSTICS,
    PLOT_SETTINGS: PLOT_SETTINGS,
    GRID_PLOT_POSITIONS: GRID_PLOT_POSITIONS,
    TOLERANCES: TOLERANCES,
    CORE_SHRINKAGE: CORE_SHRINKAGE,
    NOMINAL_COORDS: NOMINAL_COORDS
  };

  return {
    COLUMN_NAMES: COLUMN_NAMES,
    GRID_MAPPING: GRID_MAPPING,
    VTP_REGISTRATION: VTP_REGISTRATION,
    PTV_REGISTRATION: PTV_REGISTRATION,
    DIAGNOSTICS: DIAGNOSTICS,
    PLOT_SETTINGS: PLOT_SETTINGS,
    GRID_PLOT_POSITIONS: GRID_PLOT_POSITIONS,
    TOLERANCES: TOLERANCES,
    CORE_SHRINKAGE: CORE_SHRINKAGE,
    NOMINAL_COORDS: NOMINAL_COORDS,
    DEFAULT_SETTINGS: DEFAULT_SETTINGS
  };
})();
