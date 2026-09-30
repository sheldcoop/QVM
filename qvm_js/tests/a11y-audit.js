/**
 * tests/a11y-audit.js - dev only (copied from ABF Tracker v2). Loaded by tests/preview.html?audit=1.
 *
 * A small in-page accessibility audit of whatever is on screen (no library,
 * no network). Prints one console line per finding ("AUDIT FAIL ...") and a
 * summary ("AUDIT DONE n"), so a headless run can collect them.
 *
 *   names     every control, link and role=img has an accessible name
 *   labels    every form field has a label
 *   ids       no duplicate ids
 *   tabindex  no positive tabindex
 *   landmarks header, nav, main present; exactly one h1
 *   contrast  rendered text against its real background (AA: 4.5, large 3)
 *   focus     every focusable element shows a visible focus indicator
 */
(function () {
  'use strict';
  var fails = [];
  function fail(rule, el, msg) {
    fails.push(rule);
    console.log('AUDIT FAIL ' + rule + ' | ' + describe(el).replace(/"/g, "'") + ' | ' + msg);
  }
  function describe(el) {
    if (!el || !el.tagName) return String(el);
    var s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    var cls = (el.getAttribute('class') || '').trim().split(/\s+/).slice(0, 2).join('.');
    if (cls) s += '.' + cls;
    var t = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return s + (t ? ' "' + t + '"' : '');
  }
  function visible(el) {
    if (!el.isConnected) return false;
    if (el.closest('[hidden], [aria-hidden="true"], .sr-only, .tip-card')) return false;
    var r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    var cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none';
  }
  function accName(el) {
    var n = el.getAttribute('aria-label');
    if (n && n.trim()) return n.trim();
    var by = el.getAttribute('aria-labelledby');
    if (by) return by.split(/\s+/).map(function (id) { var t = document.getElementById(id); return t ? t.textContent : ''; }).join(' ').trim();
    if (el.id) {
      var lab = document.querySelector('label[for="' + el.id + '"]');
      if (lab && lab.textContent.trim()) return lab.textContent.trim();
    }
    var wrap = el.closest('label');
    if (wrap && wrap.textContent.trim()) return wrap.textContent.trim();
    if (/^(input|select|textarea)$/i.test(el.tagName)) return (el.getAttribute('title') || '').trim();
    var text = (el.textContent || '').trim();
    if (text) return text;
    return (el.getAttribute('title') || '').trim();
  }

  var root = document.body;
  var interactive = root.querySelectorAll('a[href], button, input, select, textarea, [role="button"], [role="tab"], [role="radio"], [role="menuitem"], [tabindex]');

  // names + labels
  Array.prototype.forEach.call(interactive, function (el) {
    if (!visible(el) || el.type === 'hidden') return;
    if (el.tagName === 'INPUT' && (el.type === 'radio' || el.type === 'checkbox')) {
      if (!accName(el)) fail('labels', el, 'checkbox/radio without a label');
      return;
    }
    if (!accName(el)) fail(/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) ? 'labels' : 'names', el, 'no accessible name');
  });
  Array.prototype.forEach.call(root.querySelectorAll('[role="img"]'), function (el) {
    if (visible(el) && !accName(el)) fail('names', el, 'role=img without aria-label');
  });
  Array.prototype.forEach.call(root.querySelectorAll('svg:not([aria-hidden="true"]):not([role])'), function (el) {
    if (visible(el) && !el.closest('[aria-hidden="true"]') && !el.closest('button, a') && el.getBoundingClientRect().width > 20) {
      fail('names', el, 'meaningful-looking svg without role/label (add role="img" + label, or aria-hidden)');
    }
  });

  // ids + tabindex
  var seen = {};
  Array.prototype.forEach.call(root.querySelectorAll('[id]'), function (el) {
    if (seen[el.id]) fail('ids', el, 'duplicate id "' + el.id + '"');
    seen[el.id] = true;
  });
  Array.prototype.forEach.call(root.querySelectorAll('[tabindex]'), function (el) {
    if (+el.getAttribute('tabindex') > 0) fail('tabindex', el, 'positive tabindex');
  });

  // landmarks + headings (only when the shell is showing)
  if (!document.getElementById('shell').hidden) {
    ['header', 'nav', 'main'].forEach(function (t) {
      if (!document.querySelector(t)) fail('landmarks', document.body, 'missing <' + t + '>');
    });
    var h1s = Array.prototype.filter.call(document.querySelectorAll('main h1'), visible);
    if (h1s.length !== 1) fail('landmarks', document.body, h1s.length + ' visible h1 in main (want 1)');
  }

  // contrast of rendered text
  function rgba(s) {
    var m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function over(a, b) { return [0, 1, 2].map(function (i) { return a[i] * a[3] + b[i] * (1 - a[3]); }).concat(1); }
  function lum(c) {
    var f = function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  function background(el) {
    var layers = [];
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
      var cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && n !== document.body && n !== document.documentElement &&
          cs.backgroundImage.indexOf('gradient') === -1) return null;     // text on an image: skip
      var c = rgba(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    var base = [255, 255, 255, 1];
    if (!layers.length || layers[layers.length - 1][3] < 1) base = rgba(getComputedStyle(document.body).backgroundColor) || base;
    for (var i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  }
  var checked = 0;
  var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  var done = new Set();
  while (walker.nextNode()) {
    var t = walker.currentNode;
    var el = t.parentElement;
    if (!el || done.has(el) || !t.textContent.trim()) continue;
    done.add(el);
    if (el.closest('svg') || !visible(el) || el.closest('.chart-missing')) continue;
    var cs = getComputedStyle(el);
    if (+cs.opacity < 0.95 && el.closest('.zero, .is-disabled, :disabled, .empty, [aria-disabled="true"]')) continue;
    var fg = rgba(cs.color);
    var bg = background(el);
    if (!fg || !bg) continue;
    // an ancestor's opacity fades the text too
    var op = 1;
    for (var a = el; a && a.nodeType === 1; a = a.parentElement) op *= +getComputedStyle(a).opacity;
    if (op < 0.95) {
      if (el.closest('.zero, .is-disabled, :disabled, .strip-seg.zero, .kpi-tile.is-zero, [aria-disabled="true"]')) continue;  // deliberately dimmed, WCAG exempts disabled
      fg = [fg[0], fg[1], fg[2], fg[3] * op];
    }
    if (fg[3] < 1) fg = over(fg, bg);
    var l1 = lum(fg), l2 = lum(bg);
    var ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    var size = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 700;
    var large = size >= 24 || (bold && size >= 18.66);
    checked++;
    if (ratio < (large ? 3 : 4.5)) fail('contrast', el, ratio.toFixed(2) + ':1 (' + size + 'px' + (bold ? ' bold' : '') + ')');
  }

  // focus indicator
  var focusables = Array.prototype.filter.call(
    root.querySelectorAll('a[href], button:not(:disabled), input:not(:disabled):not([type="hidden"]), select, textarea, [tabindex="0"]'),
    function (el) { return visible(el); }).slice(0, 150);
  focusables.forEach(function (el) {
    el.focus({ preventScroll: true });
    if (document.activeElement !== el) return;
    var cs = getComputedStyle(el);
    var shown = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) ||
                (cs.boxShadow && cs.boxShadow !== 'none');
    // radios/checkboxes that are visually hidden show focus on their sibling
    if (!shown && el.matches('.seg-opt input')) shown = getComputedStyle(el.nextElementSibling).outlineStyle !== 'none';
    // inputs inside instrument fields show focus on the box
    if (!shown && el.closest('.ifield-box')) shown = getComputedStyle(el.closest('.ifield-box')).boxShadow !== 'none';
    if (!shown) fail('focus', el, 'no visible focus indicator');
  });
  if (document.activeElement) document.activeElement.blur();

  // keyboard behaviour: menus and dialogs give focus back where it came from
  var steps = [];
  // only on a quiet page: a dialog or menu opened by ?click= would be toggled
  var busy = document.querySelector('dialog[open], .menu');
  var userBtn = busy ? null : document.getElementById('userBtn');
  if (userBtn && visible(userBtn)) steps.push(function (next) {
    userBtn.focus(); userBtn.click();
    setTimeout(function () {
      if (!document.querySelector('.menu')) fail('keyboard', userBtn, 'user menu did not open');
      else if (!document.querySelector('.menu').contains(document.activeElement)) fail('keyboard', userBtn, 'focus did not move into the menu');
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      setTimeout(function () {
        if (document.querySelector('.menu')) fail('keyboard', userBtn, 'Esc did not close the menu');
        if (document.activeElement !== userBtn) fail('keyboard', userBtn, 'focus not returned after the menu closed');
        next();
      }, 100);
    }, 100);
  });
  // a dialog: Lab status "Set status" (or the first "Add" button in Settings)
  var opener = document.querySelector('.tool-plate-actions button') ||
               Array.prototype.filter.call(document.querySelectorAll('#main .panel-actions button'), visible)[0];
  if (!busy && opener && visible(opener)) steps.push(function (next) {
    opener.focus(); opener.click();
    setTimeout(function () {
      var dlg = document.querySelector('dialog[open]');
      if (!dlg) { fail('keyboard', opener, 'the dialog did not open'); return next(); }
      if (!dlg.contains(document.activeElement)) fail('keyboard', opener, 'focus did not move into the dialog');
      var cancel = Array.prototype.filter.call(dlg.querySelectorAll('.modal-foot button'), function (b) { return /cancel/i.test(b.textContent); })[0];
      if (cancel) cancel.click();
      setTimeout(function () {
        if (document.querySelector('dialog[open]')) fail('keyboard', opener, 'Cancel did not close the dialog');
        if (document.activeElement !== opener) fail('keyboard', opener, 'focus not returned to the button after closing');
        next();
      }, 400);
    }, 300);
  });
  (function run(i) {
    if (i < steps.length) return steps[i](function () { run(i + 1); });
    finish();
  })(0);

  function finish() {
  console.log('AUDIT DONE ' + fails.length + ' findings, ' + checked + ' text elements, ' + focusables.length + ' focusables, theme ' +
              document.documentElement.getAttribute('data-theme') + ', keyboard steps ' + steps.length);
  }
})();
