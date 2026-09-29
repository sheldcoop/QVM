/**
 * Metrology Request Tracker - ui/overlays.js  (copied from ABF Tracker v2)
 *
 * Toasts, dialogs (confirm, reason prompt), tooltip card, popover menu.
 * Adds to QVM.ui (see ui/core.js for the load order).
 *
 * Rule: user text never reaches innerHTML. Use el()/text() or esc().
 */
(function (ui) {
  'use strict';

  var el = ui.el;
  var icon = ui.icon;
  var mount = ui.mount;
  var reducedMotion = ui.reducedMotion;

  /* ------------------------------------------------------------------ *
   * Toasts
   * ------------------------------------------------------------------ */

  /**
   * Show a toast. Every error must also be logged and shown inline by the
   * caller - a toast alone is not enough.
   * Slides in, shows a progress bar for its lifetime, pauses on hover.
   * @param {Object} o {message, kind, timeout_ms, actions:[{label, onClick}]}
   */
  function toast(o) {
    var opts = (typeof o === 'string') ? { message: o } : (o || {});
    var kind = opts.kind || 'info';
    var host = document.getElementById('toasts');
    if (!host) return null;

    var timeout = (opts.timeout_ms !== undefined) ? opts.timeout_ms
                : (kind === 'error' ? 0 : 5000); // errors stay until dismissed

    var node = el('div', { class: 'toast ' + kind + (opts.cls ? ' ' + opts.cls : ''), role: kind === 'error' ? 'alert' : null }, [
      el('span', { class: 'toast-icon' }, icon(opts.icon || (kind === 'error' ? 'alert' : kind === 'success' ? 'check' : kind === 'warning' ? 'alert' : 'info'), 18)),
      el('div', { class: 'toast-text' }, [
        el('div', { text: opts.message || '' }),
        opts.actions && opts.actions.length
          ? el('div', { class: 'toast-actions' }, opts.actions.map(function (a) {
              return el('button', {
                class: 'link', type: 'button',
                text: a.label,
                onclick: function () { dismiss(); if (a.onClick) a.onClick(); }
              });
            }))
          : null
      ]),
      el('button', { class: 'btn-icon', type: 'button', 'aria-label': 'Dismiss',
                     onclick: function () { dismiss(); } }, icon('close', 14)),
      timeout ? el('div', { class: 'toast-progress', style: { animationDuration: timeout + 'ms' } }) : null
    ]);
    host.appendChild(node);

    // hover pauses both the bar (CSS) and the timer (here)
    var remaining = timeout, startedAt = Date.now(), timer = null;
    function arm() { if (remaining > 0) { startedAt = Date.now(); timer = setTimeout(dismiss, remaining); } }
    if (timeout) {
      arm();
      node.addEventListener('mouseenter', function () {
        clearTimeout(timer); remaining -= Date.now() - startedAt;
      });
      node.addEventListener('mouseleave', arm);
    }

    var gone = false;
    function dismiss() {
      if (gone) return;
      gone = true;
      clearTimeout(timer);
      if (reducedMotion()) { remove(); return; }
      node.classList.add('leaving');
      setTimeout(remove, 190);
    }
    function remove() { if (node.parentNode) node.parentNode.removeChild(node); }
    return { dismiss: dismiss };
  }

  function toastError(message, error) {
    if (error) console.error('QVM:', message, error);
    return toast({ message: message, kind: 'error' });
  }

  /* ------------------------------------------------------------------ *
   * Dialogs
   * ------------------------------------------------------------------ */

  /**
   * Open a modal. Returns a promise resolving to the value passed by an
   * action button, or null when cancelled (Esc, backdrop, Cancel).
   * Scales and fades in over a blurred backdrop.
   * @param {Object} o {title, icon, wide, cls, body (Node), actions:[{label, value, kind, validate, submit}]}
   *
   * submit(value) -> Promise: the dialog stays open while it runs (buttons
   * off, spinner) and closes with its result; a rejection is shown INSIDE
   * the dialog, so the person can fix the entry instead of starting over.
   */
  function dialog(o) {
    return new Promise(function (resolve) {
      var host = document.getElementById('dialogHost') || document.body;
      var dlg = el('dialog', { class: 'modal' + (o.wide ? ' wide' : '') + (o.cls ? ' ' + o.cls : ''), 'aria-label': o.title || 'Dialog' });
      var settled = false;
      var opener = document.activeElement;

      function close(value) {
        if (settled) return;
        settled = true;
        function finish() {
          dlg.close();
          if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
          if (opener && opener.isConnected && opener.focus) opener.focus();
          resolve(value === undefined ? null : value);
        }
        if (reducedMotion()) return finish();
        dlg.classList.add('closing');
        setTimeout(finish, 140);
      }

      var head = el('div', { class: 'modal-head' }, [
        o.icon ? el('span', { class: 'panel-icon' }, icon(o.icon, 18)) : null,
        el('h2', { text: o.title || '' }),
        el('button', { class: 'btn-icon', type: 'button', 'aria-label': 'Close',
                       onclick: function () { close(null); } }, icon('close', 16))
      ]);

      var errBox = el('div', { class: 'modal-error', role: 'alert', hidden: true });
      var body = el('div', { class: 'modal-body' }, [o.body || null, errBox]);
      var busy = false;

      var actions = (o.actions || [{ label: 'Close', value: null }]).map(function (a) {
        var btn = el('button', {
          class: a.kind === 'primary' ? 'btn-primary' : a.kind === 'danger' ? 'btn-danger' : 'btn',
          type: 'button', text: a.label,
          onclick: function () {
            if (busy) return;
            if (a.validate) {
              var problem = a.validate();
              if (problem) return; // the validator shows the inline message
            }
            var value = a.value === undefined ? true : (typeof a.value === 'function' ? a.value() : a.value);
            if (!a.submit) return close(value);
            busy = true;
            errBox.hidden = true;
            actions.forEach(function (b) { b.disabled = true; });
            btn.classList.add('is-busy');
            Promise.resolve().then(function () { return a.submit(value); }).then(function (res) {
              busy = false;
              close(res === undefined ? value : res);
            }).catch(function (e) {
              busy = false;
              actions.forEach(function (b) { b.disabled = false; });
              btn.classList.remove('is-busy');
              mount(errBox, [icon('alert', 16), el('span', { text: (e && e.message) || String(e) })]);
              errBox.hidden = false;
            });
          }
        });
        return btn;
      });

      dlg.appendChild(head);
      dlg.appendChild(body);
      dlg.appendChild(el('div', { class: 'modal-foot' }, actions));

      // Esc closes (not while a save is running). `cancel` fires for Esc.
      dlg.addEventListener('cancel', function (e) { e.preventDefault(); if (!busy) close(null); });
      ui.linkLabels(dlg);
      host.appendChild(dlg);
      dlg.showModal();
      var first = dlg.querySelector('.modal-body input, .modal-body select, .modal-body textarea, .btn-primary, button');
      if (first) first.focus();
    });
  }

  /** Yes/no confirmation. Resolves true or false. */
  function confirm(o) {
    var opts = (typeof o === 'string') ? { message: o } : (o || {});
    return dialog({
      title: opts.title || 'Please confirm',
      icon: opts.danger ? 'alert' : 'info',
      body: el('p', { text: opts.message || '' }),
      actions: [
        { label: opts.cancelLabel || 'Cancel', value: false },
        { label: opts.confirmLabel || 'Confirm', value: true, kind: opts.danger ? 'danger' : 'primary' }
      ]
    }).then(function (v) { return v === true; });
  }

  /**
   * Ask for a mandatory reason (every correction needs one).
   * Resolves the reason string, or null if cancelled.
   */
  function promptReason(o) {
    var opts = o || {};
    var input = el('textarea', { rows: 3, id: 'reasonInput', placeholder: 'Why is this change needed?' });
    var error = el('div', { class: 'error', hidden: true, text: 'A reason is required.' });
    var fieldNode = el('div', { class: 'field' }, [
      el('label', { for: 'reasonInput', text: 'Reason' }), input, error
    ]);

    return dialog({
      title: opts.title || 'Reason required',
      icon: 'edit',
      body: el('div', {}, [opts.message ? el('p', { text: opts.message }) : null, fieldNode]),
      actions: [
        { label: 'Cancel', value: null },
        {
          label: opts.confirmLabel || 'Save', kind: 'primary',
          value: function () { return input.value.trim(); },
          validate: function () {
            var empty = input.value.trim() === '';
            error.hidden = !empty;
            fieldNode.classList.toggle('invalid', empty);
            if (empty) input.focus();
            return empty;
          }
        }
      ]
    });
  }

  /* ------------------------------------------------------------------ *
   * Tooltip card (one shared node) and popover menu
   * ------------------------------------------------------------------ */

  var tipNode = null;
  // The card lives in the open dialog when its anchor is in one: a modal
  // dialog sits in the top layer, above anything in <body>.
  function tipHost(anchor) {
    if (!tipNode) tipNode = el('div', { class: 'tip-card', role: 'tooltip', id: 'mrtTip' });
    var host = (anchor && anchor.closest && anchor.closest('dialog[open]')) || document.body;
    if (tipNode.parentNode !== host) host.appendChild(tipNode);
    return tipNode;
  }

  function showTip(target, content) {
    placeTip(target.getBoundingClientRect(), content, target);
    target.setAttribute('aria-describedby', 'mrtTip');
  }

  /** Show the tooltip card above a rectangle ({left, top, right, bottom, width, height}). */
  function placeTip(r, content, anchor) {
    var t = tipHost(anchor);
    mount(t, content);
    var w = t.offsetWidth, h = t.offsetHeight;
    var left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2));
    var top = r.top - h - 10;
    if (top < 8) top = r.bottom + 10;
    t.style.left = left + 'px';
    t.style.top = top + 'px';
    t.classList.add('show');
  }

  function hideTip(target) {
    if (tipNode) tipNode.classList.remove('show');
    if (target) target.removeAttribute('aria-describedby');
  }

  /**
   * Show a tooltip card for any element under `root` matching `selector`,
   * on hover and on keyboard focus. build(target) returns the card content.
   */
  function bindTips(root, selector, build) {
    function enter(e) {
      var t = e.target.closest && e.target.closest(selector);
      if (!t || !root.contains(t)) return;
      var content = build(t);
      if (content) showTip(t, content);
    }
    function leave(e) {
      var t = e.target.closest && e.target.closest(selector);
      if (!t) return;
      if (e.relatedTarget && t.contains(e.relatedTarget)) return;
      hideTip(t);
    }
    root.addEventListener('mouseover', enter);
    root.addEventListener('mouseout', leave);
    root.addEventListener('focusin', enter);
    root.addEventListener('focusout', leave);
  }

  /** Two-column row for a tooltip card. */
  function tipRow(label, value) {
    return el('div', { class: 'tip-row' }, [el('span', { text: label }), el('b', { text: value })]);
  }

  var openMenu = null;

  /**
   * Popover menu under an anchor button. Closes on Esc, outside click or
   * a choice. items: [{label, icon, aside, onClick} | {sep: true} | {node}]
   */
  function menu(anchor, items, head) {
    if (openMenu) { var wasSame = openMenu.anchor === anchor; openMenu.close(); if (wasSame) return null; }
    var node = el('div', { class: 'menu', role: 'menu' });
    if (head) node.appendChild(el('div', { class: 'menu-head' }, head));
    items.forEach(function (it) {
      if (it.sep) return node.appendChild(el('div', { class: 'menu-sep', role: 'separator' }));
      if (it.node) return node.appendChild(el('div', { class: 'menu-row' }, it.node));
      node.appendChild(el('button', {
        class: 'menu-item', type: 'button', role: 'menuitem',
        onclick: function () { close(); if (it.onClick) it.onClick(); }
      }, [it.icon ? icon(it.icon, 16) : null, el('span', { text: it.label }),
          it.aside ? el('span', { class: 'menu-aside', text: it.aside }) : null]));
    });
    document.body.appendChild(node);
    var r = anchor.getBoundingClientRect();
    node.style.top = (r.bottom + 8) + 'px';
    node.style.left = Math.max(8, Math.min(window.innerWidth - node.offsetWidth - 8, r.right - node.offsetWidth)) + 'px';
    anchor.setAttribute('aria-expanded', 'true');

    function onDoc(e) { if (!node.contains(e.target) && !anchor.contains(e.target)) close(); }
    function onKey(e) {
      if (e.key === 'Escape') { close(); anchor.focus(); return; }
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      var list = Array.prototype.slice.call(node.querySelectorAll('.menu-item, input'));
      var i = list.indexOf(document.activeElement);
      e.preventDefault();
      var next = list[(i + (e.key === 'ArrowDown' ? 1 : -1) + list.length) % list.length];
      if (next) next.focus();
    }
    function close() {
      document.removeEventListener('mousedown', onDoc, true);
      document.removeEventListener('keydown', onKey, true);
      anchor.setAttribute('aria-expanded', 'false');
      if (node.parentNode) node.parentNode.removeChild(node);
      openMenu = null;
    }
    document.addEventListener('mousedown', onDoc, true);
    document.addEventListener('keydown', onKey, true);
    var first = node.querySelector('.menu-item, input');
    if (first) first.focus();
    openMenu = { anchor: anchor, close: close };
    return openMenu;
  }

  /**
   * Copy text to the clipboard (a share path, a request ID) and say so.
   * Falls back to a hidden textarea where the Clipboard API is not allowed.
   */
  function copyText(text, label) {
    function done() { toast({ kind: 'success', message: (label || 'Copied') + ': ' + text, timeout_ms: 2500 }); }
    function fallback() {
      var ta = el('textarea', { class: 'sr-only', 'aria-hidden': 'true' });
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      if (ok) done(); else toast({ kind: 'warning', message: 'Could not copy. Select the text and press Ctrl+C: ' + text });
    }
    var nav = window.navigator;
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      return nav.clipboard.writeText(text).then(done, fallback);
    }
    fallback();
    return Promise.resolve();
  }

  /**
   * A side panel from the right (board, P5). body: node; foot: [node].
   * Esc, the X or a click on the dim area closes it. Returns {close}.
   */
  function drawer(o) {
    var host = document.getElementById('dialogHost') || document.body;
    var dlg = el('dialog', { class: 'drawer', 'aria-label': o.title || 'Details' });
    var opener = document.activeElement, done = false;
    function close() {
      if (done) return;
      done = true;
      function finish() {
        dlg.close();
        if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
        if (opener && opener.isConnected && opener.focus) opener.focus();
        if (o.onClose) o.onClose();
      }
      if (reducedMotion()) return finish();
      dlg.classList.add('closing');
      setTimeout(finish, 160);
    }
    dlg.appendChild(el('div', { class: 'modal-head' }, [
      o.icon ? el('span', { class: 'panel-icon' }, icon(o.icon, 18)) : null,
      el('h2', { text: o.title || '' }),
      el('button', { class: 'btn-icon', type: 'button', 'aria-label': 'Close', onclick: close }, icon('close', 16))
    ]));
    dlg.appendChild(el('div', { class: 'drawer-body' }, o.body || null));
    if (o.foot) dlg.appendChild(el('div', { class: 'drawer-foot' }, o.foot));
    dlg.addEventListener('cancel', function (e) { e.preventDefault(); close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) close(); });
    host.appendChild(dlg);
    dlg.showModal();
    var first = dlg.querySelector('.drawer-foot button, .btn-icon');
    if (first) first.focus();
    return { close: close, node: dlg };
  }

  ui.bindTips = bindTips;
  ui.copyText = copyText;
  ui.confirm = confirm;
  ui.dialog = dialog;
  ui.drawer = drawer;
  ui.hideTip = hideTip;
  ui.menu = menu;
  ui.placeTip = placeTip;
  ui.promptReason = promptReason;
  ui.showTip = showTip;
  ui.tipRow = tipRow;
  ui.toast = toast;
  ui.toastError = toastError;
})(window.QVM.ui);
