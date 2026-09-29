/**
 * Metrology Request Tracker - ui/core.js  (copied from ABF Tracker v2)
 *
 * DOM building and escaping, icons, display formatting, motion helpers,
 * status (displayStatus, chip, LED), page header.
 *
 * QVM.ui is built from plain scripts, loaded in this order:
 *   core.js, components.js, glyphs.js, heatmap.js, overlays.js, charts.js
 * Each later file adds its components to QVM.ui. No modules, so it
 * still runs from file://. ui-kit.html shows every component.
 *
 * Rule: user text never reaches innerHTML. Use el()/text() or esc().
 */
window.QVM = window.QVM || {};
window.QVM.ui = (function () {
  'use strict';

  /* ------------------------------------------------------------------ *
   * Escaping and DOM building
   * ------------------------------------------------------------------ */

  /** Escape text for the rare case where a string must go into markup. */
  function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /**
   * Build an element.
   * el('div', {class: 'card', dataset: {action: 'x'}}, ['text', childEl])
   * Text children are set with textContent, so they can never inject markup.
   */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (key) {
      var v = attrs[key];
      if (v === null || v === undefined || v === false) return;
      if (key === 'class') node.className = v;
      else if (key === 'text') node.textContent = v;
      else if (key === 'html') node.innerHTML = v;       // static markup only
      else if (key === 'dataset') Object.keys(v).forEach(function (d) { node.dataset[d] = v[d]; });
      else if (key === 'style') Object.keys(v).forEach(function (s) { node.style[s] = v[s]; });
      else if (key.indexOf('on') === 0 && typeof v === 'function') node.addEventListener(key.slice(2), v);
      else if (v === true) node.setAttribute(key, '');
      else node.setAttribute(key, v);
    });
    append(node, children);
    return node;
  }

  /** Append children. Nested arrays are flattened, so callers can group freely. */
  function append(parent, children) {
    if (children === null || children === undefined) return parent;
    (Array.isArray(children) ? children : [children]).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      if (Array.isArray(c)) return append(parent, c);
      parent.appendChild(typeof c === 'object' && c.nodeType ? c : document.createTextNode(String(c)));
    });
    return parent;
  }

  /** Replace everything inside a node. */
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function mount(node, children) { return append(clear(node), children); }

  /* ------------------------------------------------------------------ *
   * Icons - inline SVG, no emojis
   * ------------------------------------------------------------------ */

  var PATHS = {
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    lots: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 7 2.6 1.7 1.7 0 0 0 8.1 1V1a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 15 2.6h.1a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.5 1h.1a2 2 0 1 1 0 4H21a1.7 1.7 0 0 0-1.6 1z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v5M12 18h.01"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    download: '<path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M4 21h16"/>',
    upload: '<path d="M12 21v-12"/><path d="m7 13 5-5 5 5"/><path d="M4 21h16"/>',
    save: '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h7V3M8 21v-7h8v7"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5"/>',
    contrast: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18a9 9 0 0 0 0-18z" fill="currentColor"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    logo: '<circle cx="12" cy="12" r="7.5"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/><circle cx="12" cy="12" r="1.6"/>',
    inbox: '<path d="M3 12h5l2 3h4l2-3h5"/><path d="M5 5h14l2 7v7H3v-7z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    archive: '<path d="M3 3h18v4H3zM5 7v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7"/><path d="M10 12h4"/>',
    restore: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.7 2.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 3"/>',
    edit: '<path d="M17 3l4 4L7 21H3v-4z"/>',
    move: '<path d="M5 9l-3 3 3 3"/><path d="M2 12h14"/><path d="M19 15l3-3-3-3"/><path d="M22 12H8"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    filter: '<path d="M3 4h18l-7 8v6l-4 2V12z"/>',
    trash: '<path d="M4 6h16M9 6V4h6v2"/><path d="M6 6v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6"/><path d="M10 10v6M14 10v6"/>',
    home: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    chevron_left: '<path d="M15 18l-6-6 6-6"/>',
    expand: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    gauge: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 18 4-6"/><path d="M12 18h.01"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    analytics: '<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="5"/><rect x="12" y="8" width="3" height="9"/><rect x="17" y="5" width="3" height="12"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    chevron_down: '<path d="m6 9 6 6 6-6"/>',
    chevron_right: '<path d="m9 6 6 6-6 6"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    motion: '<path d="M3 8h10M3 12h14M3 16h8"/><path d="M17 8h4M19 16h2"/>',
    ruler: '<path d="M3 17 17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>',
    requests: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h3"/>',
    request_new: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M12 12v6M9 15h6"/>',
    board: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/><path d="M5 8h2M11 8h2M11 11h2M17 8h2"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    wrench: '<path d="M4 20l7.5-7.5"/><path d="M11.5 12.5a4.5 4.5 0 0 1 5.6-7.9l-2.6 2.6.9 2.5 2.5.9 2.6-2.6a4.5 4.5 0 0 1-7.9 5.6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    tag: '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    hirata: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8" cy="8.5" r="1.3"/><circle cx="8" cy="12" r="1.3"/><circle cx="8" cy="15.5" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="16" cy="8.5" r="1.3"/><circle cx="16" cy="15.5" r="1.3"/>',
    keyboard: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/>'
  };

  /** Inline SVG icon element. `name` must be one of PATHS - never user text. */
  function icon(name, size) {
    var s = size || 18;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', s);
    svg.setAttribute('height', s);
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.8');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = PATHS[name] || PATHS.alert; // static strings from this file
    return svg;
  }

  /* ------------------------------------------------------------------ *
   * Formatting (display only - never used for storage)
   * ------------------------------------------------------------------ */

  var VIENNA = 'Europe/Vienna';

  /** dd.mm.yyyy HH:MM in Europe/Vienna, 24 h. */
  function formatTs(ts) {
    if (!ts) return '-';
    var d = (ts instanceof Date) ? ts : new Date(typeof ts === 'number' ? ts : String(ts));
    if (isNaN(d.getTime())) return '-';
    var parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: VIENNA, day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).formatToParts(d).reduce(function (o, p) { o[p.type] = p.value; return o; }, {});
    return parts.day + '.' + parts.month + '.' + parts.year + ' ' + parts.hour + ':' + parts.minute;
  }

  /** dd.mm.yyyy without the time. */
  function formatDate(ts) {
    var s = formatTs(ts);
    return s === '-' ? s : s.slice(0, 10);
  }

  /** A duration in hours as "12 d 7 h" / "7 h 30 min" / "45 min". */
  function formatDurationH(hours) {
    if (!isFinite(hours)) return '-';
    if (hours < 0) hours = 0;
    // round once, then split, so 30 h 59.6 min reads 31 h, never 30 h 60 min
    if (hours < 48) {
      var mins = Math.round(hours * 60);
      if (mins < 60) return mins + ' min';
      var h = Math.floor(mins / 60), m = mins % 60;
      return m ? h + ' h ' + m + ' min' : h + ' h';
    }
    var totalH = Math.round(hours);
    var days = Math.floor(totalH / 24), rem = totalH % 24;
    return rem ? days + ' d ' + rem + ' h' : days + ' d';
  }

  /** Thousands-separated number with fixed decimals. */
  function formatNumber(value, decimals) {
    if (!isFinite(value)) return '-';
    return new Intl.NumberFormat('en-GB', {
      minimumFractionDigits: decimals || 0, maximumFractionDigits: (decimals === undefined) ? 0 : decimals
    }).format(value);
  }


  function formatPct(value) {
    return isFinite(value) ? formatNumber(value, 1) + ' %' : '-';
  }

  /**
   * Split a duration in hours into whole days, hours, minutes and seconds,
   * for a live countdown. Negative input reads as all zeros.
   */
  function countdownParts(hours) {
    var total = Math.max(0, Math.floor((isFinite(hours) ? hours : 0) * 3600));
    return {
      days: Math.floor(total / 86400),
      hours: Math.floor((total % 86400) / 3600),
      minutes: Math.floor((total % 3600) / 60),
      seconds: total % 60,
      total_seconds: total
    };
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  /* ------------------------------------------------------------------ *
   * Motion helpers
   *
   * Everything that moves checks reducedMotion() first. Two sources:
   * the OS setting, and the per-user toggle (data-motion on <html>).
   * ------------------------------------------------------------------ */

  function reducedMotion() {
    if (document.documentElement.getAttribute('data-motion') === 'reduce') return true;
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  /**
   * Pause CSS animations while a node is off-screen. One shared observer;
   * nodes that left the DOM are dropped every so often so it never leaks.
   */
  var offscreenIO = null;
  var offscreenNodes = [];
  function watchOffscreen(node) {
    if (!node || !('IntersectionObserver' in window)) return node;
    if (!offscreenIO) {
      offscreenIO = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { e.target.classList.toggle('offscreen', !e.isIntersecting); });
      }, { rootMargin: '80px' });
    }
    offscreenIO.observe(node);
    offscreenNodes.push(node);
    if (offscreenNodes.length % 64 === 0) {
      offscreenNodes = offscreenNodes.filter(function (n) {
        if (n.isConnected) return true;
        offscreenIO.unobserve(n);
        return false;
      });
    }
    return node;
  }

  /** Stagger the entrance of a container's children, 40 ms apart. */
  function stagger(container) {
    var kids = container.children;
    for (var i = 0; i < kids.length; i++) kids[i].style.setProperty('--i', Math.min(i, 14));
    container.classList.add('stagger');
    return container;
  }

  /** Replace a container's content with a short fade (tab panels). */
  function fadeSwap(container, children) {
    mount(container, children);
    container.classList.remove('fade-in');
    void container.offsetWidth; // restart the animation
    container.classList.add('fade-in');
    return container;
  }

  /** Count a number up from 0 on first paint. Text only. */
  function countUp(node, to, opts) {
    var o = opts || {};
    var fmt = o.format || function (v) { return formatNumber(v, o.decimals || 0); };
    if (!isFinite(to) || reducedMotion() || o.animate === false) { node.textContent = fmt(to); return; }
    var dur = o.duration || 900;
    var from = o.from || 0;
    var t0 = null;
    function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur);
      var eased = 1 - Math.pow(1 - k, 3);
      node.textContent = fmt(from + (to - from) * eased);
      if (k < 1) requestAnimationFrame(step);
    }
    node.textContent = fmt(from);
    requestAnimationFrame(step);
  }

  /** 12345 -> "12 345" with a narrow no-break space, for big readouts. */
  function groupDigits(n) {
    return String(Math.floor(Math.abs(n))).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /* ------------------------------------------------------------------ *
   * Status
   * ------------------------------------------------------------------ */

  var STATUS_LABEL = {
    ok: 'OK', warning: 'Warning', critical: 'Critical',
    expired: 'Expired', blocked: 'Blocked', neutral: 'Unknown'
  };


  /**
   * THE one place that decides which status the UI shows.
   * Accepts a status name or an object {status, expired, blocked};
   * expired wins over blocked. Request statuses, lateness and priorities
   * are mapped onto these five in M2/M3.
   *
   * @param {Object|string} stats a status name or a status object
   * @returns {string} ok | warning | critical | expired | blocked | neutral
   */
  function displayStatus(stats) {
    if (!stats) return 'neutral';
    if (typeof stats === 'string') return stats;
    if (stats.expired) return 'expired';
    if (stats.blocked) return 'blocked';
    return stats.status || 'neutral';
  }

  /** Status chip. Accepts a status name or a status object. Blocked gets a lock. */
  function statusChip(statusResult) {
    var name = displayStatus(statusResult);
    var label = STATUS_LABEL[name] || STATUS_LABEL.neutral;
    return el('span', { class: 'chip ' + name + (name === 'blocked' ? ' has-icon' : '') }, [
      name === 'blocked' ? icon('lock', 11) : null,
      label
    ]);
  }

  /** A small status light. Critical and Expired pulse. */
  function led(status, label) {
    var s = displayStatus(status);
    var live = s === 'critical' || s === 'expired';
    var node = el('span', { class: 'led ' + s + (live ? ' live' : ''), 'aria-hidden': label ? null : 'true' });
    if (label) { node.setAttribute('role', 'img'); node.setAttribute('aria-label', label); }
    return live ? watchOffscreen(node) : node;
  }

  /**
   * THE way to show a status (DECISIONS T-8): its icon + its word, never colour alone.
   * status: ok | warning | critical | expired | blocked | neutral. The icon shape comes from
   * css/app.css (--ic-*): tick, triangle, stop octagon, clock, lock.
   *   ui.statusBadge('expired', 'Late')      a chip: icon + word
   *   ui.statusIcon('critical')              the icon alone, beside words you already show
   */
  var STATUS_KINDS = ['ok', 'warning', 'critical', 'expired', 'blocked', 'neutral'];
  function statusBadge(status, text, o) {
    var s = STATUS_KINDS.indexOf(status) === -1 ? 'neutral' : status;
    return el('span', { class: 'chip ' + s + (o && o.cls ? ' ' + o.cls : ''), title: (o && o.title) || null, text: text });
  }
  function statusIcon(status) {
    var s = STATUS_KINDS.indexOf(status) === -1 ? 'neutral' : status;
    return el('span', { class: 'st-ic is-' + s, 'aria-hidden': 'true' });
  }

  var seq = 0;
  function uid(prefix) { seq += 1; return prefix + seq; }

  /**
   * Tie each form label to its control for assistive tech. Many forms are
   * built as <div.field><label>Text</label><input></div>; a label without
   * `for` is not linked. For every .field, give the first control
   * an id if it has none and point the label at it; further controls in the
   * same field get an aria-label. Safe to run repeatedly.
   */
  var labelSeq = 0;
  function linkLabels(root) {
    if (!root || !root.querySelectorAll) return root;
    Array.prototype.forEach.call(root.querySelectorAll('.field, .ifield'), function (f) {
      var label = f.querySelector(':scope > label, :scope > .ifield-label');
      var controls = Array.prototype.filter.call(
        f.querySelectorAll('input:not([type="hidden"]), select, textarea'),
        function (x) { return !label || !label.contains(x); });
      if (!label || !controls.length) return;
      var text = label.textContent.trim();
      // the label names the first control; any others (a "custom value" box,
      // a second part) are named after it plus their own placeholder
      var ctl = controls[0];
      if (!ctl.id) { labelSeq += 1; ctl.id = 'lbl' + labelSeq; }
      if (label.tagName === 'LABEL') label.setAttribute('for', ctl.id);
      else if (!ctl.getAttribute('aria-label')) ctl.setAttribute('aria-label', text);
      controls.slice(1).forEach(function (other) {
        if (!other.getAttribute('aria-label')) {
          other.setAttribute('aria-label', text + ' - ' + (other.getAttribute('placeholder') || 'value'));
        }
      });
    });
    return root;
  }

  /** Page header with a title, optional subtitle and right-aligned actions. */
  function pageHead(title, subtitle, actions) {
    return el('div', { class: 'page-head' }, [
      el('div', {}, [
        el('h1', { text: title }),
        subtitle ? el('div', { class: 'page-sub', text: subtitle }) : null
      ]),
      el('div', { class: 'spacer' }),
      actions || null
    ]);
  }

  /** Initials for the user avatar, e.g. "Prince Khurana" -> "PK". */
  function initials(name) {
    return String(name || '?').trim().split(/\s+/).slice(0, 2)
      .map(function (w) { return w[0].toUpperCase(); }).join('');
  }


  return {
    STATUS_LABEL: STATUS_LABEL,
    append: append,
    clear: clear,
    countUp: countUp,
    countdownParts: countdownParts,
    displayStatus: displayStatus,
    el: el,
    esc: esc,
    fadeSwap: fadeSwap,
    formatDate: formatDate,
    formatDurationH: formatDurationH,
    formatNumber: formatNumber,
    formatPct: formatPct,
    formatTs: formatTs,
    groupDigits: groupDigits,
    icon: icon,
    initials: initials,
    led: led,
    statusBadge: statusBadge,
    statusIcon: statusIcon,
    mount: mount,
    pad2: pad2,
    pageHead: pageHead, linkLabels: linkLabels,
    reducedMotion: reducedMotion,
    stagger: stagger,
    statusChip: statusChip,
    uid: uid,
    watchOffscreen: watchOffscreen
  };
})();
