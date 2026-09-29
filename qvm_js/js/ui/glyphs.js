/**
 * Metrology Request Tracker - ui/glyphs.js
 *
 * Tool glyphs: one line drawing per kind of tool, as an engineer would
 * sketch it on a whiteboard. The admin picks a glyph per tool in Settings,
 * so a new tool needs no code change (it can use the generic reticle).
 *
 *   ui.toolGlyph('fib', {size: 40, state: 'live', label: 'FIB', rate: 2, alert: true, destructive: true})
 *     state: 'idle' (default) | 'live' (working: its parts move - P1)
 *            | 'maint' (dashed amber beam) | 'off' (Down: dimmed, warning lamp blinks)
 *     rate: animation speed multiplier (queue length); alert: red pulse (late);
 *     destructive: the FIB cut variant when the tool mills (auto-mapped, P1)
 *   Living icons (v2): moving parts carry tx-* classes whose duration is
 *   var(--tx-d) = base x slow / rate; .tx-work dims when Down; .tx-alert is
 *   the late pulse; .tx-detail fades in on hover. Still drawings are complete
 *   last frames, so idle and Reduce motion show the finished picture.
 *   ui.toolGlyphState(node, state)   change it later without a redraw
 *   ui.GLYPHS                        [{key, label}] for the Settings dropdown
 *
 * Parts (styled in css/app.css, "Tool glyphs"): tg-body (the instrument),
 * tg-detail, tg-sample (the panel under test), tg-block (solid sample),
 * tg-beam / tg-dot (the probe, beam or scan path, in the accent colour).
 *
 * Adds to QVM.ui (see ui/core.js for the load order).
 * Rule: user text never reaches innerHTML. Only static strings from this
 * file are used as SVG markup.
 */
(function (ui) {
  'use strict';

  /*
   * Drawn on a 48 x 48 grid, stroke 2 - living instrument scenes (look over
   * physics, never noisy: at most 3 moving parts each). Moving parts carry
   * tx-* classes (see the header); still drawings are complete last frames:
   *   HRM microscope field: breathing lens, drawing caliper, diameter tick
   *   AOI golden vs scan: sweeping bar, blinking defects, recording dot
   *   PRF via cut: gliding stylus, drawing profile
   *   QVM layer shift: nudging arrow, turning lock ring, pulsing via
   *   FIB ion trench: glowing raster beam, shimmer, sparks, opening face
   *   FIB-destructive: the wide deep trench, banks flying, hatched face
   *   generic: turning reticle (fallback for any other tool)
   *   tg-lamp    warning lamp, shown and blinking only when the tool is Down
   *   tx-alert   red ring, pulsing on alert (late) or Down; tx-detail fades
   *              in on hover with the reading (depth, defects, shift, width)
   */
  var LAMP = '<circle class="tg-lamp" cx="42" cy="6" r="3"/>';
  var DRAW = {
    // HRM, living: the microscope field - breathing lens, drawing caliper,
    // pulsing diameter tick. Hover reads the trace width.
    hrm: '<defs><filter id="txh-hrm" x="0" y="0" width="100%" height="100%">' +
         '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>' +
         '<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35 0 0 0 0 0.69 0 0 0 0 1 0 0 0 0.5 0"/></filter></defs>' +
         '<circle class="tg-body tx tx-focus" style="--tx-base:2.4s" cx="24" cy="15" r="11"/>' +
         '<circle class="tx tx-shimmer" style="--tx-base:3s;fill:var(--accent-soft)" cx="24" cy="15" r="11" filter="url(#txh-hrm)" stroke="none"/>' +
         '<circle class="tg-detail" cx="24" cy="15" r="6.5"/>' +
         '<path class="tg-detail" d="M24 6.5V10M24 20v3.5M15.5 15h3.5M29 15h3.5"/>' +
         '<circle class="tg-sample" cx="10" cy="36" r="4.5"/>' +
         '<path class="tg-detail tx tx-blink" style="--tx-base:1.2s" d="M6.8 32.8l6.4 6.4"/>' +
         '<path class="tg-sample" d="M20 33h20M20 40h20"/>' +
         '<g class="tx-work">' +
         '<path class="tg-beam tx tx-draw" style="--tx-base:1.6s" d="M40 31v11M38 31h4M38 42h4"/>' +
         '</g>' +
         '<circle class="tx-alert" cx="40" cy="36.5" r="8"/>' +
         '<g class="tx-detail"><rect class="tg-detail" x="2" y="28" width="15" height="9" rx="1"/>' +
         '<text class="tx-text" x="4" y="35">0.35</text></g>' + LAMP,

    // AOI, living: golden reference vs scanned panel - the scan bar sweeps
    // the scan half, defect boxes blink, the camera recording dot pulses.
    // Hover names the defect count; the red ring only pulses on alert/Down.
    aoi: '<rect class="tg-body" x="14" y="4" width="20" height="10" rx="2"/>' +
         '<circle class="tg-detail" cx="30" cy="9" r="1.5"/>' +
         '<circle class="tg-dot tx tx-blink" style="--tx-base:.5s" cx="18" cy="9" r="1.4"/>' +
         '<path class="tg-beam" d="M20 14l-6 12M28 14l6 12" stroke-dasharray="3 3"/>' +
         '<rect class="tg-sample" x="4" y="30" width="40" height="12" rx="1"/>' +
         '<path class="tg-sample" d="M24 30v12" stroke-opacity=".5"/>' +
         '<path class="tg-detail" d="M8 34h8M8 38h8"/>' +
         '<g class="tx-work">' +
         '<rect class="tg-defect tx tx-blink" style="--tx-base:1s" x="28" y="33" width="4" height="3"/>' +
         '<rect class="tg-defect tg-d2 tx tx-blink" style="--tx-base:1s" x="35" y="37" width="3" height="3"/>' +
         '<rect class="tg-scan tx tx-sweep" style="--tx-base:2.4s" x="29" y="28" width="10" height="16" rx="1"/>' +
         '</g>' +
         '<circle class="tx-alert" cx="34" cy="36" r="9"/>' +
         '<g class="tx-detail"><rect class="tg-detail" x="27" y="32" width="14" height="9" rx="1"/>' +
         '<text class="tx-text" x="29" y="39">2 DEF</text></g>' + LAMP,

    // FIB-destructive, living: the wide deep trench - banks flying, the face
    // fully open with hatch, heavier shimmer. Auto-picked for destructive FIB.
    'fib-destructive': '<defs><filter id="txg-fibx" x="-40%" y="-40%" width="180%" height="180%">' +
         '<feGaussianBlur stdDeviation="1.1"/></filter>' +
         '<filter id="txh-fibx" x="0" y="0" width="100%" height="100%">' +
         '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>' +
         '<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35 0 0 0 0 0.69 0 0 0 0 1 0 0 0 0.5 0"/></filter></defs>' +
         '<path class="tg-body" d="M13 4h22l-6 13h-10z"/>' +
         '<path class="tg-detail" d="M16 9h16"/>' +
         '<rect class="tx tx-shimmer" style="--tx-base:2.2s" x="15" y="5" width="18" height="11" filter="url(#txh-fibx)"/>' +
         '<g class="tx-work">' +
         '<path class="tg-beam tx tx-raster" style="--tx-base:.9s" d="M24 17v13" filter="url(#txg-fibx)" stroke-width="3.5"/>' +
         '<path class="tg-beam tx tx-raster" style="--tx-base:.9s" d="M24 17v13"/>' +
         '<g class="tx tx-blink" style="--tx-base:.5s"><circle class="tg-dot" cx="14" cy="28" r="1.4"/>' +
         '<circle class="tg-dot" cx="34" cy="26" r="1.4"/><circle class="tg-dot" cx="31" cy="30" r="1.2"/></g>' +
         '<path class="tg-block" d="M4 30h40v10H4z"/>' +
         '<path class="tg-sample" d="M16 30v12M32 30v12"/>' +
         '<path class="tg-face tx tx-mill" style="--tx-base:.9s" d="M16 33h16M16 36h16M16 39h16"/>' +
         '<path class="tg-detail" d="M18 33l4 9M24 33l4 9" stroke-opacity=".6"/>' +
         '</g>' +
         '<circle class="tx-alert" cx="24" cy="36" r="10"/>' +
         '<g class="tx-detail"><path class="tg-detail" d="M35 32v9M33.5 32h3M33.5 41h3"/>' +
         '<text class="tx-text" x="26" y="30">12.4</text></g>' + LAMP,

    // PRF, living: the stylus gliding over the via cut - top diameter and
    // depth arrows, tapered walls, the profile drawing behind the tip.
    // Hover reads the depth; the red ring only pulses on alert/Down.
    prf: '<path class="tg-detail" d="M6 8h18"/>' +
         '<circle class="tg-body tx tx-blink" style="--tx-base:.9s" cx="24" cy="8" r="2"/>' +
         '<g class="tx tx-glide" style="--tx-base:2.6s"><path class="tg-detail" d="M8 8v17"/>' +
         '<circle class="tg-dot" cx="8" cy="26.5" r="1.6"/></g>' +
         '<path class="tg-beam tx tx-draw" style="--tx-base:2.6s" d="M4 26h14l3 10h6l3-10h14"/>' +
         '<g class="tx-work">' +
         '<path class="tg-block" d="M4 32h40v10H4z"/>' +
         '<path class="tg-sample" d="M19 32l2.5 10h5L29 32"/>' +
         '<path class="tg-detail" d="M19 28.5h10M19 27v3M29 27v3"/>' +
         '<path class="tg-detail" d="M43 32v10M41.5 32h3M41.5 42h3"/>' +
         '</g>' +
         '<circle class="tx-alert" cx="24" cy="37" r="10"/>' +
         '<g class="tx-detail"><rect class="tg-detail" x="2" y="30" width="15" height="9" rx="1"/>' +
         '<text class="tx-text" x="4" y="37">2.1</text></g>' + LAMP,

    // QVM, living: two shifted layers - pad below, via above, the shift
    // arrow nudging between them, the lock ring turning, the via pulsing.
    // Hover reads the shift; the red ring only pulses on alert/Down.
    qvm: '<defs><filter id="txh-qvm" x="0" y="0" width="100%" height="100%">' +
         '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>' +
         '<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35 0 0 0 0 0.69 0 0 0 0 1 0 0 0 0.5 0"/></filter></defs>' +
         '<rect class="tg-body" x="18" y="3" width="12" height="9" rx="2"/>' +
         '<rect class="tx tx-shimmer" style="--tx-base:2.8s" x="19" y="4" width="10" height="7" filter="url(#txh-qvm)"/>' +
         '<path class="tg-beam" d="M21 12l-4 12M27 12l4 12" stroke-dasharray="3 3"/>' +
         '<rect class="tg-sample" x="6" y="34" width="26" height="7"/>' +
         '<rect class="tg-sample" x="12" y="27" width="26" height="7"/>' +
         '<circle class="tg-sample" cx="15" cy="37.5" r="3"/>' +
         '<circle class="tg-dot tx tx-blink" style="--tx-base:.8s" cx="23" cy="30.5" r="1.8"/>' +
         '<path class="tg-beam tg-shift tx tx-nudge" style="--tx-base:1.8s" d="M15 37.5l7-6M19.5 31.5h2.5M22 34v-2.5"/>' +
         '<g class="tx tx-turn" style="--tx-base:6s"><path class="tg-beam tg-reticle" d="M15 28.5v3M15 43.5v3M6 37.5h3M21 37.5h3"/></g>' +
         '<circle class="tx-alert" cx="15" cy="37.5" r="9"/>' +
         '<g class="tx-detail"><rect class="tg-detail" x="25" y="33" width="15" height="9" rx="1"/>' +
         '<text class="tx-text" x="27" y="40">0.8</text></g>' + LAMP,

    // FIB, living: the ion column over its trench - glowing raster beam,
    // holographic shimmer on the column, sparks, the milled face opening.
    // Hover shows the trench depth; the red ring only pulses on alert/Down.
    fib: '<defs><filter id="txg-fib" x="-40%" y="-40%" width="180%" height="180%">' +
         '<feGaussianBlur stdDeviation="1.1"/></filter>' +
         '<filter id="txh-fib" x="0" y="0" width="100%" height="100%">' +
         '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>' +
         '<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35 0 0 0 0 0.69 0 0 0 0 1 0 0 0 0.5 0"/></filter></defs>' +
         '<path class="tg-body" d="M15 4h18l-5 13h-8z"/>' +
         '<path class="tg-detail" d="M17.5 9h13"/>' +
         '<rect class="tx tx-shimmer" style="--tx-base:2.6s" x="17" y="5" width="14" height="11" filter="url(#txh-fib)"/>' +
         '<g class="tx-work">' +
         '<path class="tg-beam tx tx-raster" style="--tx-base:1.1s" d="M24 17v15" filter="url(#txg-fib)" stroke-width="3.5"/>' +
         '<path class="tg-beam tx tx-raster" style="--tx-base:1.1s" d="M24 17v15"/>' +
         '<path class="tg-beam tx tx-blink" style="--tx-base:.7s" d="M20 32l-3-2M28 32l3-2" stroke-opacity=".7"/>' +
         '<path class="tg-block" d="M4 32h40v10H4z"/>' +
         '<path class="tg-sample" d="M20 32v10M28 32v10"/>' +
         '<path class="tg-face tx tx-mill" style="--tx-base:1s" d="M20 34.5h8M20 37.5h8M20 40.5h8"/>' +
         '</g>' +
         '<circle class="tx-alert" cx="24" cy="37" r="9"/>' +
         '<g class="tx-detail"><path class="tg-detail" d="M31 33v9M29.5 33h3M29.5 42h3"/>' +
         '<text class="tx-text" x="34" y="39">8.2</text></g>' + LAMP,

    // generic, living: the measuring reticle - slow-turning ring, pulsing
    // centre, quiet shimmer. Fallback for any other tool.
    generic: '<defs><filter id="txh-gen" x="0" y="0" width="100%" height="100%">' +
             '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" result="n"/>' +
             '<feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35 0 0 0 0 0.69 0 0 0 0 1 0 0 0 0.5 0"/></filter></defs>' +
             '<circle class="tg-body" cx="24" cy="24" r="14"/>' +
             '<circle class="tx tx-shimmer" style="--tx-base:3.4s;fill:var(--accent-soft)" cx="24" cy="24" r="14" filter="url(#txh-gen)" stroke="none"/>' +
             '<path class="tg-detail" d="M24 5v9M24 34v9M5 24h9M34 24h9"/>' +
             '<g class="tx-work">' +
             '<circle class="tg-beam tx tx-turn" style="--tx-base:6s" cx="24" cy="24" r="6" stroke-dasharray="4 3"/>' +
             '<circle class="tg-dot tx tx-blink" style="--tx-base:1.4s" cx="24" cy="24" r="1.8"/>' +
             '</g>' +
             '<circle class="tx-alert" cx="24" cy="24" r="11"/>' +
             '<g class="tx-detail"><circle class="tg-detail" cx="24" cy="24" r="10" stroke-dasharray="2 2"/></g>' + LAMP
  };

  var GLYPHS = [
    { key: 'hrm', label: 'Microscope (HRM)' },
    { key: 'aoi', label: 'Inspection camera (AOI)' },
    { key: 'prf', label: 'Via profiler (PRF)' },
    { key: 'qvm', label: 'Overlay optics (QVM)' },
    { key: 'fib', label: 'Ion cutter (FIB)' },
    { key: 'fib-destructive', label: 'Ion cut, destructive (FIB)' },
    { key: 'generic', label: 'Measuring reticle (any tool)' }
  ];

  var STATES = ['idle', 'live', 'maint', 'off'];

  function toolGlyphState(node, state) {
    var s = STATES.indexOf(state) === -1 ? 'idle' : state;
    STATES.forEach(function (x) { node.classList.toggle('is-' + x, x === s); });
    ui.watchOffscreen(node);   // pause the motion off-screen (live, alert and maint loops)
    return node;
  }

  /**
   * Build a tool glyph. `key` is one of GLYPHS (unknown keys draw the
   * reticle). With a label it is an image for screen readers; without,
   * it is decoration next to text that already names the tool.
   * @param {string} key
   * @param {Object} o {size, state, label, rate, alert, destructive}
   */
  function toolGlyph(key, o) {
    o = o || {};
    var k = (key === 'fib' && o.destructive && DRAW['fib-destructive']) ? 'fib-destructive' : key;
    var size = o.size || 32;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 48 48');
    svg.setAttribute('width', size);
    svg.setAttribute('height', size);
    svg.setAttribute('class', 'tool-glyph');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    if (o.label) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', o.label); }
    else svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = DRAW[k] || DRAW.generic;   // static strings from this file
    svg.dataset.glyph = DRAW[k] ? k : 'generic';
    if (o.rate && isFinite(o.rate) && o.rate > 0) svg.style.setProperty('--tx-rate', o.rate);
    if (o.alert) svg.classList.add('is-alert');
    return toolGlyphState(svg, o.state);
  }

  ui.GLYPHS = GLYPHS;
  ui.toolGlyph = toolGlyph;
  ui.toolGlyphState = toolGlyphState;
})(window.QVM.ui);
