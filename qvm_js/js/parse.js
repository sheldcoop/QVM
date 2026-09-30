/**
 * QVM Dashboard - parse.js
 *
 * Unified QVM registration parser: one coordinate-first engine for Pad-to-Via
 * and Via-to-Pad exports, plus filename metadata and per-file ingest.
 * Faithful port of qvm_dashboard/src/parser.py + upload_metadata.py +
 * ingestion.py. Rows are plain objects with stable internal keys (mm units);
 * display labels resolve at render time via COLUMN_NAMES.
 *
 * Pure, except ingestFile takes already-decoded text (the view reads the
 * FileReader result). Throws QVMParseError on empty/garbage input.
 */
window.QVM = window.QVM || {};
window.QVM.parse = (function () {
  'use strict';

  function QVMParseError(message) {
    this.name = 'QVMParseError';
    this.message = message || 'QVM parse error';
  }
  QVMParseError.prototype = Object.create(Error.prototype);
  QVMParseError.prototype.constructor = QVMParseError;

  var PTS_RE = /From\s+(\d+)\s*Pts\./;
  var PANEL_RE = /(?:panel[\s_]*|(?:^|[_\s-])p)(\d+)(?=$|[_\s-])/i;
  var SIDE_RE = /(?:^|[_\s-])(front|back|[fb])(?=$|[_\s-])/i;
  var BU_RE = /(?:^|[_\s-])bu[-_\s]?(\d+)(?=$|[_\s-])/i;
  var CIRCLE_RE = /^Circle:\s*(.+?)\s*\(/;
  var LOC_RE = /\b([UL][LR])[_ \s-]?(\d)\b/i;

  function settingsOrDefault(settings) {
    return settings || window.QVM.defaults.DEFAULT_SETTINGS;
  }

  /* ---------------- filename ---------------- */

  function parseFilename(filename) {
    var base = String(filename || '').split(/[\\/]/).pop();
    var stem = base.replace(/\.[^.]*$/, '');
    var lower = stem.toLowerCase();
    var hasVtp = lower.indexOf('vtp') !== -1 || lower.indexOf('via to pad') !== -1;
    var hasPtv = lower.indexOf('ptv') !== -1 || lower.indexOf('pad to via') !== -1;
    var formatHint = null;
    if (hasVtp && !hasPtv) formatHint = 'Via to Pad';
    else if (hasPtv && !hasVtp) formatHint = 'Pad to Via';

    var panel = 'Unknown', side = 'Unknown', buildUp = 'Unknown', m;
    if ((m = PANEL_RE.exec(stem))) panel = m[1];
    if ((m = SIDE_RE.exec(stem))) {
      var tok = m[1].toLowerCase();
      side = (tok === 'f' || tok === 'front') ? 'F' : 'B';
    }
    if ((m = BU_RE.exec(stem))) buildUp = 'BU-' + m[1];

    return { formatHint: formatHint, panel: panel, side: side, buildUp: buildUp };
  }

  /* ---------------- site extraction ---------------- */

  function canonicalLocation(raw) {
    var m = LOC_RE.exec(raw || '');
    if (!m) return '';
    return m[1].toUpperCase() + '_' + m[2];
  }

  function locationFromCircle(label) {
    if (!label) return '';
    var direct = canonicalLocation(label.trim());
    if (direct) return direct;
    var lowered = label.toLowerCase();
    ['via', 'pad'].forEach(function (token) {
      lowered = lowered.replace(new RegExp('(^|[_\\s-])' + token + '($|[_\\s-])', 'gi'), '_');
    });
    return canonicalLocation(lowered);
  }

  function circleKind(label) {
    var s = (label || '').toLowerCase();
    var hasVia = s.indexOf('via') !== -1, hasPad = s.indexOf('pad') !== -1;
    if (hasVia && !hasPad) return 'via';
    if (hasPad && !hasVia) return 'pad';
    return null;
  }

  function distanceProcessHint(label) {
    var s = (label || '').toLowerCase();
    if (s.indexOf('ptv') !== -1) return 'Pad to Via';
    if (s.indexOf('vtp') !== -1 || s.indexOf('btp') !== -1) return 'Via to Pad';
    return null;
  }

  function newSite() {
    return { circles: [], activeIdx: null, untypedDiams: [], untypedCoords: [],
             pendingX: null, distanceLabel: '', sc: null, dx: null, dy: null };
  }

  function valueAfterEquals(s) {
    var i = String(s).indexOf('=');
    if (i === -1) return null;
    var v = parseFloat(String(s).slice(i + 1).trim());
    return isNaN(v) ? null : v;
  }

  function addCoord(site, axis, value) {
    if (value === null || value === undefined) return;
    var idx = site.activeIdx;
    if (idx !== null && idx >= 0 && idx < site.circles.length) {
      site.circles[idx][axis] = value;
      return;
    }
    if (axis === 'x') { site.pendingX = value; return; }
    if (site.pendingX === null || site.pendingX === undefined) return;
    site.untypedCoords.push([site.pendingX, value]);
    site.pendingX = null;
  }

  function extractSites(content) {
    var sites = [], site = newSite(), m;
    String(content || '').split(/\r?\n/).forEach(function (line) {
      var s = line.trim();
      if (!s) return;
      if ((m = CIRCLE_RE.exec(s))) {
        var label = m[1].trim();
        var pts = PTS_RE.exec(s);
        site.circles.push({ label: label, kind: circleKind(label),
          location: locationFromCircle(label),
          pts: pts ? parseInt(pts[1], 10) : null, x: null, y: null, diameter: null });
        site.activeIdx = site.circles.length - 1;
        return;
      }
      if (s.indexOf('Distance:') === 0) { site.distanceLabel = s; site.activeIdx = null; return; }
      if (s.indexOf('Coord.') === 0 && s.indexOf('X') !== -1) { addCoord(site, 'x', valueAfterEquals(s)); return; }
      if (s.indexOf('Coord.') === 0 && s.indexOf('Y') !== -1) { addCoord(site, 'y', valueAfterEquals(s)); return; }
      if (s.indexOf('Diameter') !== -1) {
        var val = valueAfterEquals(s), idx = site.activeIdx;
        if (idx !== null && idx >= 0 && idx < site.circles.length) site.circles[idx].diameter = val;
        else site.untypedDiams.push(val);
        return;
      }
      if (s.indexOf('SC') === 0) { site.sc = valueAfterEquals(s); return; }
      if (s.indexOf('DX') === 0) { site.dx = valueAfterEquals(s); return; }
      if (s.indexOf('DY') === 0) {
        site.dy = valueAfterEquals(s);
        sites.push(site);
        site = newSite();
      }
    });
    return sites;
  }

  function resolveSite(site) {
    var circles = site.circles;
    var via = null, pad = null, i;
    for (i = 0; i < circles.length; i++) {
      if (!via && circles[i].kind === 'via') via = circles[i];
      if (!pad && circles[i].kind === 'pad') pad = circles[i];
    }
    if (!via && circles.length) via = circles[0];
    if (!pad && circles.length > 1) pad = circles[1];

    var diams = (site.untypedDiams || []).slice();
    var coords = (site.untypedCoords || []).slice();
    var viaDiam = via ? via.diameter : null;
    var padDiam = pad ? pad.diameter : null;
    if (viaDiam === null || viaDiam === undefined) viaDiam = diams.length ? diams.shift() : null;
    if (padDiam === null || padDiam === undefined) padDiam = diams.length ? diams.shift() : null;

    var viaXY = (via && via.x !== null && via.x !== undefined && via.y !== null && via.y !== undefined)
      ? [via.x, via.y] : (coords.length ? coords.shift() : null);
    var padXY = (pad && pad.x !== null && pad.x !== undefined && pad.y !== null && pad.y !== undefined)
      ? [pad.x, pad.y] : (coords.length ? coords.shift() : null);

    var hint = '';
    if (via && via.location) hint = via.location;
    else if (pad && pad.location) hint = pad.location;

    var proc = distanceProcessHint(site.distanceLabel || '');
    if (proc === null) {
      var viaIdx = -1, padIdx = -1;
      for (i = 0; i < circles.length; i++) {
        if (viaIdx === -1 && circles[i].kind === 'via') viaIdx = i;
        if (padIdx === -1 && circles[i].kind === 'pad') padIdx = i;
      }
      if (viaIdx !== -1 && padIdx !== -1) proc = viaIdx < padIdx ? 'Via to Pad' : 'Pad to Via';
    }

    return {
      locationHint: hint,
      viaDiameter: viaDiam, padDiameter: padDiam,
      viaX: viaXY ? viaXY[0] : null, viaY: viaXY ? viaXY[1] : null,
      padX: padXY ? padXY[0] : null, padY: padXY ? padXY[1] : null,
      viaPts: via ? via.pts : null, padPts: pad ? pad.pts : null,
      sc: site.sc, dx: site.dx, dy: site.dy, processHint: proc
    };
  }

  function pickProcess(sites) {
    var vtp = 0, ptv = 0;
    sites.forEach(function (s) {
      if (s.processHint === 'Via to Pad') vtp++;
      else if (s.processHint === 'Pad to Via') ptv++;
    });
    return vtp >= ptv ? 'Via to Pad' : 'Pad to Via';
  }

  /* ---------------- coordinate-first locations ---------------- */

  function quadrant(cx, cy, x, y) {
    if (x < cx && y >= cy) return 'UL';
    if (x < cx && y < cy) return 'LL';
    if (x >= cx && y < cy) return 'LR';
    return 'UR';
  }

  function permutations(arr, n) {
    if (n === 0) return [[]];
    var out = [];
    for (var i = 0; i < arr.length; i++) {
      var rest = arr.slice(0, i).concat(arr.slice(i + 1));
      permutations(rest, n - 1).forEach(function (tail) { out.push([arr[i]].concat(tail)); });
    }
    return out;
  }

  function assignIndexes(points) {
    // points: [[siteIdx, x, y]] → {siteIdx: 1..4} by best corner-template fit.
    if (!points.length) return {};
    if (points.length === 1) { var single = {}; single[points[0][0]] = 1; return single; }
    var xs = points.map(function (p) { return p[1]; });
    var ys = points.map(function (p) { return p[2]; });
    var templates = { 1: [Math.min.apply(null, xs), Math.max.apply(null, ys)],
                      2: [Math.min.apply(null, xs), Math.min.apply(null, ys)],
                      3: [Math.max.apply(null, xs), Math.min.apply(null, ys)],
                      4: [Math.max.apply(null, xs), Math.max.apply(null, ys)] };
    var n = Math.min(points.length, 4), best = null, bestAssign = {};
    permutations([1, 2, 3, 4], n).forEach(function (perm) {
      var total = 0, local = {};
      for (var k = 0; k < n; k++) {
        var t = templates[perm[k]];
        total += Math.pow(points[k][1] - t[0], 2) + Math.pow(points[k][2] - t[1], 2);
        local[points[k][0]] = perm[k];
      }
      if (best === null || total < best) { best = total; bestAssign = local; }
    });
    if (points.length > 4) {
      var used = {};
      Object.keys(bestAssign).forEach(function (k) { used[bestAssign[k]] = true; });
      points.slice(4).forEach(function (p) {
        var bi = 1, bd = null;
        [1, 2, 3, 4].forEach(function (idx) {
          if (used[idx]) return;
          var t = templates[idx];
          var d = Math.pow(p[1] - t[0], 2) + Math.pow(p[2] - t[1], 2);
          if (bd === null || d < bd) { bd = d; bi = idx; }
        });
        bestAssign[p[0]] = bi;
        used[bi] = true;
      });
    }
    return bestAssign;
  }

  function siteXY(s) {
    if (s.viaX !== null && s.viaX !== undefined && s.viaY !== null && s.viaY !== undefined)
      return [s.viaX, s.viaY];
    if (s.padX !== null && s.padX !== undefined && s.padY !== null && s.padY !== undefined)
      return [s.padX, s.padY];
    return null;
  }

  function assignLocations(sites, settings, warnings) {
    settings = settingsOrDefault(settings);
    var grid = settings.GRID_MAPPING || {};
    var diag = settings.DIAGNOSTICS || {};
    var fallbackCx = parseFloat(diag.panel_center_x !== undefined ? diag.panel_center_x : 255.0);
    var fallbackCy = parseFloat(diag.panel_center_y !== undefined ? diag.panel_center_y : 257.5);

    var observed = [];
    sites.forEach(function (s) { var xy = siteXY(s); if (xy) observed.push(xy); });

    var cx, cy;
    if (observed.length >= 4) {
      var xs = observed.map(function (p) { return p[0]; }).sort(function (a, b) { return a - b; });
      var ys = observed.map(function (p) { return p[1]; }).sort(function (a, b) { return a - b; });
      var mid = Math.floor(observed.length / 2);
      if (observed.length % 2 === 0) {
        cx = (xs[mid - 1] + xs[mid]) / 2;
        cy = (ys[mid - 1] + ys[mid]) / 2;
      } else { cx = xs[mid]; cy = ys[mid]; }
    } else { cx = fallbackCx; cy = fallbackCy; }

    var quads = { UL: [], LL: [], LR: [], UR: [] };
    sites.forEach(function (s, i) {
      var xy = siteXY(s);
      if (!xy) return;
      quads[quadrant(cx, cy, xy[0], xy[1])].push([i, xy[0], xy[1]]);
    });

    var resolved = {};
    Object.keys(quads).forEach(function (q) {
      var assigned = assignIndexes(quads[q]);
      Object.keys(assigned).forEach(function (k) { resolved[k] = q + '_' + assigned[k]; });
    });

    sites.forEach(function (s, i) {
      var loc = resolved[i] || '', hint = s.locationHint || '';
      if (hint && !loc) loc = hint;
      if (hint && loc && hint !== loc) {
        warnings.push('Site ' + i + ': coordinate-based location ' + JSON.stringify(loc) +
          ' differs from header location ' + JSON.stringify(hint) + '; using coordinates.');
      }
      s.location = loc;
      s.gridId = (loc && grid[loc] !== undefined) ? grid[loc] : null;
      if (!loc) warnings.push('Site ' + i + ': could not resolve location from coordinates.');
    });
  }

  /* ---------------- SC normalisation + rows ---------------- */

  function normalizeSc(sites, settings, process, warnings) {
    settings = settingsOrDefault(settings);
    var key = process === 'Via to Pad' ? 'VTP_REGISTRATION' : 'PTV_REGISTRATION';
    var cfg = settings[key] || {};
    var enabled = cfg.sc_override_enabled !== undefined ? !!cfg.sc_override_enabled : true;
    var absUm = parseFloat(cfg.sc_override_abs_error_um !== undefined ? cfg.sc_override_abs_error_um : 100.0);
    var relPct = parseFloat(cfg.sc_override_rel_error_pct !== undefined ? cfg.sc_override_rel_error_pct : 10.0);

    sites.forEach(function (site, i) {
      if (site.dx === null || site.dx === undefined || site.dy === null || site.dy === undefined) return;
      var calc = Math.hypot(site.dx, site.dy);
      if (site.sc === null || site.sc === undefined) {
        site.sc = calc;
        warnings.push('Site ' + i + ': SC missing in source; replaced with sqrt(DX^2+DY^2) = ' +
          (calc * 1000).toFixed(1) + ' um.');
        return;
      }
      var absErrUm = Math.abs(site.sc - calc) * 1000;
      var calcUm = Math.abs(calc) * 1000;
      var relErr = calcUm > 0 ? (absErrUm / calcUm) * 100 : (absErrUm === 0 ? 0 : Infinity);
      var mismatch = absErrUm > absUm && relErr > relPct;
      if (mismatch && enabled) {
        site.sc = calc;
        warnings.push('Site ' + i + ': SC mismatch detected (parsed=' + (site.sc * 1000).toFixed(1) +
          ' um). Using calculated SC.');
      } else if (mismatch) {
        warnings.push('Site ' + i + ': SC mismatch detected. Keeping parsed SC per configuration.');
      }
    });
  }

  function emitRow(s, process) {
    return {
      location: s.location || '', gridId: s.gridId,
      padDiameter: s.padDiameter, viaDiameter: s.viaDiameter,
      coordX: s.viaX, coordY: s.viaY,
      sc: s.sc, dx: s.dx, dy: s.dy,
      padPts: s.padPts, viaPts: s.viaPts,
      process: process, panel: 'Unknown', side: 'Unknown', buildUp: 'Unknown'
    };
  }

  function parseQvmContent(content, settings) {
    settings = settingsOrDefault(settings);
    var warnings = [];
    var raw = extractSites(content);
    if (!raw.length) throw new QVMParseError('No valid measurement blocks found in the file.');
    var sites = raw.map(resolveSite);
    if (!sites.length) throw new QVMParseError('No valid measurement blocks found in the file.');
    var process = pickProcess(sites);
    assignLocations(sites, settings, warnings);
    normalizeSc(sites, settings, process, warnings);

    var rows = sites.map(function (s) { return emitRow(s, process); });

    var key = process === 'Via to Pad' ? 'VTP_REGISTRATION' : 'PTV_REGISTRATION';
    var capUm = parseFloat((settings[key] || {}).outlier_cap_um !== undefined
      ? settings[key].outlier_cap_um : 1000.0);
    var capMm = capUm / 1000;
    rows.forEach(function (r) {
      if (r.sc !== null && r.sc !== undefined && Math.abs(r.sc) > capMm) {
        warnings.push('Grid ID ' + r.gridId + ': SC = ' + (r.sc * 1000).toFixed(1) +
          ' µm — exceeds outlier cap ' + capUm.toFixed(0) + ' µm.');
      }
    });
    if (!rows.length) throw new QVMParseError('No valid measurement blocks found in the file.');
    return { rows: rows, warnings: warnings, process: process };
  }

  /* ---------------- metadata + ingest ---------------- */

  function normalizeBuildUp(value) {
    if (value === null || value === undefined) return null;
    var raw = String(value).trim();
    if (!raw || raw.toLowerCase() === 'unknown') return null;
    var m = raw.match(/^bu[-_\s]?(\d+)$/i);
    if (m) return 'BU-' + ('00' + m[1]).slice(-2);
    if (/^\d+$/.test(raw)) return 'BU-' + ('00' + raw).slice(-2);
    return raw;
  }

  function resolveOverride(overrideValue, parsedValue) {
    if (overrideValue !== null && overrideValue !== undefined && String(overrideValue).trim() !== '')
      return String(overrideValue).trim();
    if (parsedValue !== null && parsedValue !== undefined && String(parsedValue).trim() !== '')
      return String(parsedValue).trim();
    return 'Unknown';
  }

  function resolveMetadata(filenameInfo, detectedProcess, override) {
    override = override || {};
    var processOverride = override.processOverride || null;
    var panelOverride = override.panelOverride || null;
    var sideOverride = override.sideOverride || null;
    return {
      finalProcess: processOverride || detectedProcess || null,
      finalPanel: resolveOverride(panelOverride, filenameInfo.panel),
      finalSide: resolveOverride(sideOverride, filenameInfo.side),
      parsedPanel: filenameInfo.panel,
      parsedSide: filenameInfo.side,
      processOverride: processOverride,
      panelOverride: panelOverride,
      sideOverride: sideOverride
    };
  }

  function ingestFile(name, text, settings, override, defaultBuildUp) {
    settings = settingsOrDefault(settings);
    override = override || {};
    var buOverride = normalizeBuildUp(override.buildUp);
    var parsed = parseQvmContent(text, settings);
    var rows = parsed.rows, parseWarnings = parsed.warnings;
    var detected = rows.length ? rows[0].process : null;
    var filenameInfo = parseFilename(name);
    var parsedBU = normalizeBuildUp(filenameInfo.buildUp);
    var resolved = resolveMetadata(filenameInfo, detected, {
      processOverride: override.process || null,
      panelOverride: override.panel || null,
      sideOverride: override.side || null
    });

    var uiWarnings = [];
    if (resolved.processOverride) {
      if (detected && resolved.processOverride !== detected) {
        uiWarnings.push('`' + name + '`: override sets type to ' + resolved.processOverride +
          ' (content detected ' + detected + '). Using override.');
      }
      rows.forEach(function (r) { r.process = resolved.finalProcess; });
    } else if (!filenameInfo.formatHint) {
      uiWarnings.push('`' + name + '`: filename has no VTP/PTV hint. Treated as ' +
        detected + ' from content.');
    } else if (detected && filenameInfo.formatHint !== detected) {
      uiWarnings.push('`' + name + '`: filename hints ' + filenameInfo.formatHint +
        ' but content is ' + detected + '. Going with the content.');
    }

    if (resolved.panelOverride && resolved.parsedPanel !== 'Unknown' &&
        resolved.panelOverride !== resolved.parsedPanel) {
      uiWarnings.push('`' + name + '`: override sets panel to ' + resolved.panelOverride +
        ' (filename panel ' + resolved.parsedPanel + '). Using override.');
    }
    if (resolved.sideOverride && resolved.parsedSide !== 'Unknown' &&
        resolved.sideOverride !== resolved.parsedSide) {
      uiWarnings.push('`' + name + '`: override sets side to ' + resolved.sideOverride +
        ' (filename side ' + resolved.parsedSide + '). Using override.');
    }

    var bu = buOverride || parsedBU || normalizeBuildUp(defaultBuildUp) || 'Unknown';
    rows.forEach(function (r) {
      r.panel = resolved.finalPanel;
      r.side = resolved.finalSide;
      r.buildUp = bu;
      r.annularRing = window.QVM.domain.annularRing(r);
    });

    return { rows: rows, parseWarnings: parseWarnings, uiWarnings: uiWarnings,
             meta: resolved, filenameInfo: filenameInfo };
  }

  /* ---------------- Core Shrinkage files ---------------- */

  var CS_CIRCLE_RE = /Circle:\s*(?:Pad_)?([A-Z]{2})_(\d+)/i;

  function parseCsFilename(filename) {
    var stem = String(filename || '').split(/[\\/]/).pop().replace(/\.[^.]*$/, '');
    var lower = stem.toLowerCase();
    var isCs = lower.indexOf('core_shrinkage') !== -1 || lower.indexOf('core shrinkage') !== -1;
    var panel = 'Unknown', m = PANEL_RE.exec(stem);
    if (m) panel = m[1];
    var layer = 'Unknown';
    if (lower.indexOf('front') !== -1) layer = 'Front';
    else if (lower.indexOf('back') !== -1) layer = 'Back';
    return { isCoreShrinkage: isCs, panel: panel, layer: layer };
  }

  /**
   * Circle-coordinate-only text: Circle → Coord X → Coord Y → Diameter.
   * Returns {rows, warning} — empty rows with a warning, never a throw
   * (mirrors the Python parser, which logs and returns an empty frame).
   */
  function parseCsContent(content, layer, settings) {
    settings = settingsOrDefault(settings);
    var grid = settings.GRID_MAPPING || {};
    var rows = [], state = 'IDLE';
    var loc = null, quad = null, num = null, pts = null, cx = null, cy = null;
    String(content || '').split(/\r?\n/).forEach(function (raw) {
      var line = raw.trim(), m;
      if (!line) return;
      if (line.indexOf('Circle:') !== -1) {
        m = CS_CIRCLE_RE.exec(line);
        if (m) {
          quad = m[1].toUpperCase(); num = parseInt(m[2], 10);
          loc = quad + '_' + num;
          var pm = PTS_RE.exec(line);
          pts = pm ? parseInt(pm[1], 10) : null;
          state = 'X';
        } else state = 'IDLE';
        return;
      }
      if (state === 'IDLE' || line.indexOf('=') === -1) return;
      var val = parseFloat(line.split('=', 2)[1].trim());
      if (isNaN(val)) return;
      if (state === 'X' && line.indexOf('Coord. X') !== -1) { cx = val; state = 'Y'; }
      else if (state === 'Y' && line.indexOf('Coord. Y') !== -1) { cy = val; state = 'DIAM'; }
      else if (state === 'DIAM' && line.indexOf('Diameter') !== -1) {
        rows.push({ location: loc, quadrant: quad, pointNum: num,
          coordX: cx, coordY: cy, diameter: val, pts: pts, layer: layer,
          process: 'Core Shrinkage', gridId: grid[loc] !== undefined ? grid[loc] : null,
          panel: 'Unknown', side: 'Unknown', buildUp: 'Unknown' });
        state = 'IDLE';
      }
    });
    return { rows: rows,
             warning: rows.length ? null : 'No circles parsed from ' + layer + ' layer.' };
  }

  function ingestCsFile(name, text, settings, override) {
    settings = settingsOrDefault(settings);
    override = override || {};
    var info = parseCsFilename(name);
    var layer = (override.layer && override.layer !== '') ? override.layer : info.layer;
    var parsed = parseCsContent(text, layer === 'Unknown' ? 'Front' : layer, settings);
    var rows = parsed.rows;
    var panel = resolveOverride(override.panel, info.panel);
    var bu = normalizeBuildUp(override.buildUp) || 'Unknown';
    rows.forEach(function (r) {
      r.layer = layer;
      r.panel = panel;
      r.buildUp = bu;
    });
    var uiWarnings = [];
    if (parsed.warning) uiWarnings.push('`' + name + '`: ' + parsed.warning);
    if (layer === 'Unknown')
      uiWarnings.push('`' + name + '`: no Front/Back layer in the filename; treated as Front.');
    return { rows: rows, parseWarnings: [], uiWarnings: uiWarnings,
             meta: { layer: layer, panel: panel }, filenameInfo: info };
  }

  return {
    QVMParseError: QVMParseError,
    parseFilename: parseFilename,
    parseQvmContent: parseQvmContent,
    normalizeBuildUp: normalizeBuildUp,
    resolveMetadata: resolveMetadata,
    ingestFile: ingestFile,
    parseCsFilename: parseCsFilename,
    parseCsContent: parseCsContent,
    ingestCsFile: ingestCsFile
  };
})();
