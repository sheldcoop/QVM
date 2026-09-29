/**
 * Metrology Request Tracker - ui/components.js  (copied from ABF Tracker v2)
 *
 * Panel, buttons, segmented control, checkbox/switch, instrument field,
 * form (field specs -> controls -> values), KPI tile, tabs, empty state, skeleton.
 * Adds to QVM.ui (see ui/core.js for the load order).
 *
 * Rule: user text never reaches innerHTML. Use el()/text() or esc().
 */
(function (ui) {
  'use strict';

  var STATUS_LABEL = ui.STATUS_LABEL;
  var append = ui.append;
  var clear = ui.clear;
  var countUp = ui.countUp;
  var displayStatus = ui.displayStatus;
  var el = ui.el;
  var formatNumber = ui.formatNumber;
  var groupDigits = ui.groupDigits;
  var icon = ui.icon;
  var led = ui.led;
  var mount = ui.mount;
  var reducedMotion = ui.reducedMotion;
  var uid = ui.uid;
  var watchOffscreen = ui.watchOffscreen;

  /* ------------------------------------------------------------------ *
   * Panel
   * ------------------------------------------------------------------ */

  /**
   * A console panel: title bar (icon, uppercase label, optional LED,
   * actions) and a body. Returns {node, body, setStatus}.
   * @param {Object} o {title, icon, status, actions, body, cls, flush, glow, tag}
   */
  function panel(o) {
    o = o || {};
    var ledHost = el('span', { class: 'panel-led' });
    var collapseBtn = o.collapsible ? el('button', { type: 'button', class: 'panel-collapse', 'aria-expanded': 'true',
      'aria-label': 'Collapse ' + (o.title || 'panel') }) : null;
    var collapsed = !!o.collapsed;
    if (collapseBtn) {
      collapseBtn.appendChild(icon('chevron_down', 16));
      collapseBtn.addEventListener('click', function () { setCollapsed(!collapsed); });
    }
    var head = (o.title || o.actions) ? el('div', { class: 'panel-head' }, [
      o.icon ? el('span', { class: 'panel-icon' }, icon(o.icon, 16)) : null,
      o.title ? el('h2', { class: 'panel-title', text: o.title }) : null,
      ledHost,
      o.actions ? el('div', { class: 'panel-actions' }, o.actions) : null,
      collapseBtn
    ]) : null;
    var body = el('div', { class: 'panel-body' + (o.flush ? ' flush' : '') }, o.body || null);
    var node = el(o.tag || 'section', {
      class: 'panel' + (o.cls ? ' ' + o.cls : ''),
      'aria-label': o.title || null
    }, [head, body]);
    function setCollapsed(c, silent) {
      if (!collapseBtn) return;
      collapsed = !!c;
      if (collapsed) body.setAttribute('hidden', '');
      else body.removeAttribute('hidden');
      node.classList.toggle('is-collapsed', collapsed);
      collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseBtn.setAttribute('aria-label', (collapsed ? 'Expand ' : 'Collapse ') + (o.title || 'panel'));
      if (o.onToggle && !silent) o.onToggle(collapsed);
    }
    if (collapsed) setCollapsed(true, true);

    function setStatus(status) {
      var s = status ? displayStatus(status) : null;
      mount(ledHost, s ? led(s, STATUS_LABEL[s]) : null);
      if (o.glow && (s === 'critical' || s === 'expired')) node.setAttribute('data-status', s);
      else node.removeAttribute('data-status');
    }
    if (o.status) setStatus(o.status);
    return { node: node, body: body, setStatus: setStatus, setCollapsed: setCollapsed };
  }

  /* ------------------------------------------------------------------ *
   * Buttons and choices
   * ------------------------------------------------------------------ */

  /**
   * button('Save', {kind: 'primary'|'danger'|'ghost', icon, size: 'sm'|'lg',
   *                 dataset, disabled, onClick, title, ariaLabel})
   */
  function button(label, o) {
    o = o || {};
    var cls = { primary: 'btn-primary', danger: 'btn-danger', ghost: 'btn-ghost' }[o.kind] || 'btn';
    if (o.size) cls += ' btn-' + o.size;
    if (o.cls) cls += ' ' + o.cls;
    return el('button', {
      class: cls, type: o.type || 'button', disabled: !!o.disabled,
      title: o.title || null, dataset: o.dataset || null,
      'aria-label': o.ariaLabel || null, onclick: o.onClick || null
    }, [o.icon ? icon(o.icon, 16) : null, label ? el('span', { text: label }) : null]);
  }

  /**
   * Segmented control: a radio group that looks like a switch bank.
   * Arrow keys move between options (native radio behaviour).
   * @param {Object} o {label, options:[{value, label, icon, disabled}], value, onChange, name}
   */
  function segmented(o) {
    var name = o.name || uid('seg');
    var current = o.value;
    var inputs = [];
    var node = el('div', { class: 'seg', role: 'radiogroup', 'aria-label': o.label || null });
    o.options.forEach(function (opt) {
      var input = el('input', {
        type: 'radio', name: name, value: String(opt.value),
        checked: String(opt.value) === String(current), disabled: !!opt.disabled
      });
      input.addEventListener('change', function () {
        if (!input.checked) return;
        current = opt.value;
        if (o.onChange) o.onChange(opt.value);
      });
      inputs.push(input);
      node.appendChild(el('label', { class: 'seg-opt' }, [
        input, el('span', {}, [opt.icon ? icon(opt.icon, 14) : null, opt.label])
      ]));
    });
    function set(v) {
      current = v;
      inputs.forEach(function (i) { i.checked = i.value === String(v); });
    }
    return { node: node, set: set, value: function () { return current; } };
  }

  /** A labelled checkbox or switch. kind: 'check' (default) or 'switch'. */
  function toggle(o) {
    var input = el('input', { type: 'checkbox', checked: !!o.checked, disabled: !!o.disabled,
                              role: o.kind === 'switch' ? 'switch' : null });
    if (o.onChange) input.addEventListener('change', function () { o.onChange(input.checked); });
    var node = el('label', { class: o.kind === 'switch' ? 'switch' : 'check' }, [input, el('span', { text: o.label })]);
    return { node: node, input: input };
  }

  /* ------------------------------------------------------------------ *
   * Instrument field
   * ------------------------------------------------------------------ */

  /**
   * A labelled input that looks like an instrument readout: dark well,
   * mono digits, unit inside the field, validity edge line and message.
   * Returns {node, input, setState(state, message), value()}.
   * @param {Object} o {label, id, name, type, value, unit, hint, placeholder,
   *                    mono, min, max, step, inputmode, required, disabled,
   *                    options:[{value,label}], multiline, cls,
   *                    list:[{value,label}] - suggestions to type from (a datalist)}
   */
  /**
   * Combo box: a text input with a custom filter popup (replaces datalist).
   * Free text stays allowed: typing a new value is a new entry, Enter keeps it.
   * Keyboard: Down opens, Up/Down move, Enter picks (or keeps typed text),
   * Escape closes. Returns the same shape as field().
   * @param {Object} o {label, value, placeholder, hint, mono, cls, items:[{value,label}], id, name}
   */
  var comboOpen = null;   // the one open popup; one shared outside-click closer
  var comboDocArmed = false;
  function comboArmDoc() {
    if (comboDocArmed) return;
    comboDocArmed = true;
    document.addEventListener('click', function (ev) {
      if (comboOpen && comboOpen.isOpen() && !comboOpen.inside(ev.target)) comboOpen.close();
    });
  }

  function comboBox(o) {
    o = o || {};
    comboArmDoc();
    var id = o.id || uid('combo');
    var msgId = id + '-msg';
    var items = (o.items || []).map(function (x) {
      return { value: String(x.value !== undefined && x.value !== null ? x.value : ''),
               label: x.label !== undefined && x.label !== null ? String(x.label) : '' };
    });
    var input = el('input', {
      id: id, name: o.name || null, type: 'text',
      class: 'ifield-input combo-input' + (o.mono ? ' mono' : ''),
      value: o.value !== undefined && o.value !== null ? String(o.value) : null,
      placeholder: o.placeholder || null, autocomplete: 'off',
      role: 'combobox', 'aria-expanded': 'false', 'aria-autocomplete': 'list',
      'aria-controls': id + '-pop', 'aria-describedby': msgId
    });
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('spellcheck', 'false');
    var pop = el('div', { class: 'combo-pop', id: id + '-pop', role: 'listbox', hidden: true });
    var wrap = el('div', { class: 'combo-wrap' }, [input, pop]);
    var msg = el('div', { class: 'ifield-msg', id: msgId, 'aria-live': 'polite' }, o.hint || null);
    var node = el('div', { class: 'ifield combo' + (o.cls ? ' ' + o.cls : '') }, [
      el('label', { class: 'ifield-label', for: id }, [o.label || '']),
      el('div', { class: 'ifield-box combo-box' }, [wrap]),
      msg
    ]);
    var open = false, active = -1, shown = [];

    function norm(s) { return String(s || '').toLowerCase(); }
    function matches(it, q) {
      if (!q) return true;
      return norm(it.value).indexOf(q) !== -1 || norm(it.label).indexOf(q) !== -1;
    }
    function paint() {
      clear(pop);
      var q = norm(input.value.trim());
      var exact = false;
      shown = items.filter(function (it) { return matches(it, q); }).slice(0, 50);
      shown.forEach(function (it) { if (norm(it.value) === q || norm(it.label) === q) exact = true; });
      if (!shown.length) {
        pop.appendChild(el('div', { class: 'combo-none', text: q ? 'No match - press Enter to add as new' : 'No entries' }));
      } else {
        shown.forEach(function (it, i) {
          var opt = el('div', {
            class: 'combo-opt' + (i === active ? ' is-active' : ''),
            role: 'option', id: id + '-opt-' + i,
            'aria-selected': i === active ? 'true' : 'false'
          }, [
            el('span', { class: 'combo-val' + (o.mono ? ' mono' : ''), text: it.value }),
            it.label ? el('span', { class: 'combo-sub', text: it.label }) : null
          ]);
          opt.addEventListener('mousedown', function (ev) {
            ev.preventDefault();
            pick(i);
          });
          opt.addEventListener('mousemove', function () { setActive(i); });
          pop.appendChild(opt);
        });
      }
      if (q && !exact) {
        pop.appendChild(el('div', { class: 'combo-new', text: 'New: ' + input.value.trim() }));
      }
    }
    function setActive(i) {
      active = i;
      var kids = pop.querySelectorAll('.combo-opt');
      for (var k = 0; k < kids.length; k++) {
        var on = k === i;
        kids[k].classList.toggle('is-active', on);
        kids[k].setAttribute('aria-selected', on ? 'true' : 'false');
      }
      if (i >= 0) {
        input.setAttribute('aria-activedescendant', id + '-opt-' + i);
        var sel = pop.querySelectorAll('.combo-opt')[i];
        if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: 'nearest' });
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    }
    function setOpen(v) {
      open = v;
      if (v) {
        if (comboOpen && comboOpen !== api) comboOpen.close();
        comboOpen = api;
        active = -1; paint(); pop.hidden = false;
      } else {
        pop.hidden = true; setActive(-1);
        if (comboOpen === api) comboOpen = null;
      }
      input.setAttribute('aria-expanded', v ? 'true' : 'false');
    }
    function fire(name) {
      var ev;
      try { ev = new Event(name, { bubbles: true }); }
      catch (e) { ev = document.createEvent('Event'); ev.initEvent(name, true, true); }
      input.dispatchEvent(ev);
    }
    function pick(i) {
      var it = shown[i];
      if (!it) return;
      input.value = it.value;
      setOpen(false);
      fire('input');
      fire('change');
    }
    input.addEventListener('focus', function () { setOpen(true); });
    input.addEventListener('input', function () { if (!open) setOpen(true); else paint(); });
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'Down') {
        ev.preventDefault();
        if (!open) setOpen(true);
        setActive(Math.min(active + 1, shown.length - 1));
      } else if (ev.key === 'ArrowUp' || ev.key === 'Up') {
        ev.preventDefault();
        setActive(Math.max(active - 1, -1));
      } else if (ev.key === 'Enter') {
        if (open && active >= 0) { ev.preventDefault(); pick(active); }
        else if (open) setOpen(false);
      } else if (ev.key === 'Escape' || ev.key === 'Esc') {
        if (open) { ev.preventDefault(); setOpen(false); }
      }
    });
    input.addEventListener('blur', function () {
      window.setTimeout(function () { if (open) setOpen(false); }, 120);
    });

    function setState(state, message) {
      node.classList.toggle('is-valid', state === 'valid');
      node.classList.toggle('is-invalid', state === 'invalid');
      input.setAttribute('aria-invalid', state === 'invalid' ? 'true' : 'false');
      clear(msg);
      if (message) {
        append(msg, [icon(state === 'invalid' ? 'alert' : 'check', 14), el('span', { text: message })]);
      } else if (o.hint) {
        msg.textContent = o.hint;
      }
    }
    var api = { node: node, input: input, setState: setState,
             value: function () { return input.value; },
             isOpen: function () { return open; },
             inside: function (t) { return wrap.contains(t); },
             close: function () { setOpen(false); },
             setItems: function (list) {
               items = (list || []).map(function (x) {
                 return { value: String(x.value !== undefined && x.value !== null ? x.value : ''),
                          label: x.label !== undefined && x.label !== null ? String(x.label) : '' };
               });
               if (open) paint();
             } };
    if (o.disabled) { input.disabled = true; node.classList.add('is-disabled'); }
    return api;
  }

  function field(o) {
    o = o || {};
    if (o.list && o.combo) return comboBox({ label: o.label, value: o.value, placeholder: o.placeholder,
      hint: o.hint, mono: o.mono !== undefined ? o.mono : true, cls: o.cls, items: o.list, id: o.id, name: o.name, disabled: o.disabled });
    var id = o.id || uid('fld');
    var msgId = id + '-msg';
    var mono = o.mono !== undefined ? o.mono : (o.type === 'number' || !!o.unit);
    var control;
    if (o.options) {
      control = el('select', { id: id, name: o.name || null, class: 'ifield-input' },
        o.options.map(function (opt) {
          return el('option', { value: opt.value, text: opt.label,
                                selected: String(opt.value) === String(o.value) });
        }));
      if (o.value !== undefined && o.value !== null) control.value = String(o.value);
    } else if (o.multiline) {
      control = el('textarea', { id: id, name: o.name || null, class: 'ifield-input', rows: o.rows || 3,
                                 placeholder: o.placeholder || null });
      if (o.value !== undefined) control.value = o.value;
    } else {
      control = el('input', {
        id: id, name: o.name || null, type: o.type || 'text',
        class: 'ifield-input' + (mono ? ' mono' : ''),
        value: o.value !== undefined && o.value !== null ? String(o.value) : null,
        placeholder: o.placeholder || null, min: o.min, max: o.max, step: o.step,
        inputmode: o.inputmode || (o.type === 'number' ? 'decimal' : null),
        required: !!o.required, autocomplete: 'off', list: o.list ? id + '-list' : null
      });
    }
    var datalist = o.list ? el('datalist', { id: id + '-list' }, o.list.map(function (x) { return el('option', { value: x.value, label: x.label || null }); })) : null;
    control.setAttribute('aria-describedby', msgId);
    var msg = el('div', { class: 'ifield-msg', id: msgId, 'aria-live': 'polite' }, o.hint || null);
    var node = el('div', { class: 'ifield' + (o.cls ? ' ' + o.cls : '') }, [
      el('label', { class: 'ifield-label', for: id }, [
        o.label || '',
        o.unit ? el('span', { class: 'sr-only', text: ' (' + o.unit + ')' }) : null
      ]),
      el('div', { class: 'ifield-box' }, [
        control, datalist,
        o.unit ? el('span', { class: 'ifield-unit', text: o.unit, 'aria-hidden': 'true' }) : null
      ]),
      msg
    ]);
    if (o.disabled) { control.disabled = true; node.classList.add('is-disabled'); }

    function setState(state, message) {
      node.classList.toggle('is-valid', state === 'valid');
      node.classList.toggle('is-invalid', state === 'invalid');
      control.setAttribute('aria-invalid', state === 'invalid' ? 'true' : 'false');
      clear(msg);
      if (message) {
        append(msg, [icon(state === 'invalid' ? 'alert' : 'check', 14), el('span', { text: message })]);
      } else if (o.hint) {
        msg.textContent = o.hint;
      }
    }
    return { node: node, input: control, setState: setState, value: function () { return control.value; } };
  }

  /* ------------------------------------------------------------------ *
   * KPI tile
   * ------------------------------------------------------------------ */

  /**
   * KPI tile with a count-up on first paint.
   * @param {Object} o {label, value, status, icon, sub, href, decimals, animate}
   */
  function kpiTile(o) {
    var st = o.status || 'neutral';
    var valueEl = el('div', { class: 'kpi-tile-value' });
    var subEl = o.sub !== undefined ? el('div', { class: 'kpi-tile-sub', text: o.sub }) : null;
    var node = el(o.href ? 'a' : 'div', { class: 'kpi-tile ' + st, href: o.href || null }, [
      el('div', { class: 'kpi-tile-head' }, [
        el('span', { class: 'kpi-tile-label' }, [st !== 'neutral' ? ui.statusIcon(st) : null, o.label]),   // status = icon + word (T-8)
        o.icon ? el('span', { class: 'kpi-tile-icon' }, icon(o.icon, 18)) : null
      ]),
      valueEl,
      subEl
    ]);
    function paintFlags(v) {
      node.classList.toggle('is-zero', v === 0);
      node.classList.toggle('is-live', v > 0 && (st === 'critical' || st === 'expired'));
    }
    paintFlags(o.value);
    // whole numbers group with a thin space, like every other readout
    function fmt(v) { return o.decimals ? formatNumber(v, o.decimals) : groupDigits(Math.round(v)); }
    countUp(valueEl, o.value, { format: fmt, animate: o.animate });
    function update(v, sub) {
      valueEl.textContent = fmt(v);
      if (subEl && sub !== undefined) subEl.textContent = sub;
      paintFlags(v);
    }
    return { node: node, update: update };
  }


  /* ------------------------------------------------------------------ *
   * Empty states and skeletons
   * ------------------------------------------------------------------ */

  /** The empty-state illustration: a scope with the topic icon at its core. */
  function emptyArt(iconName) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 120 120');
    svg.setAttribute('class', 'empty-art');
    svg.setAttribute('aria-hidden', 'true');
    // static markup from this file only
    svg.innerHTML =
      '<path class="ea-grid" d="M8 60h104M60 8v104" stroke-dasharray="2 5" fill="none"/>' +
      '<circle class="ea-ring" cx="60" cy="60" r="52" stroke-opacity=".2"/>' +
      '<circle class="ea-ring" cx="60" cy="60" r="40" stroke-opacity=".35" stroke-dasharray="3 6"/>' +
      '<g class="ea-orbit"><circle class="ea-dot" cx="60" cy="8" r="3"/>' +
      '<circle class="ea-dot" cx="112" cy="60" r="2" opacity=".55"/>' +
      '<circle class="ea-dot" cx="23" cy="97" r="2" opacity=".35"/></g>' +
      '<circle class="ea-core" cx="60" cy="60" r="26"/>';
    var mark = icon(iconName || 'inbox', 28);
    mark.setAttribute('x', '46');
    mark.setAttribute('y', '46');
    svg.appendChild(mark);
    return watchOffscreen(svg);
  }

  function emptyState(o) {
    return el('div', { class: 'empty' }, [
      emptyArt(o.icon || 'inbox'),
      el('h2', { text: o.title || 'Nothing here yet' }),
      o.text ? el('p', { text: o.text }) : null,
      o.actionLabel ? el('button', {
        class: 'btn-primary', type: 'button', text: o.actionLabel,
        onclick: o.onAction || function () {}
      }) : null
    ]);
  }

  function skeleton(rows) {
    var n = rows || 5;
    var kids = [];
    for (var i = 0; i < n; i++) {
      kids.push(el('div', { class: 'skeleton-row', style: { width: (60 + (i % 4) * 12) + '%' } }));
    }
    return el('div', { class: 'skeleton', 'aria-busy': 'true', 'aria-label': 'Loading' }, kids);
  }

  /**
   * Tab bar with a sliding underline. Arrow keys move between tabs.
   * Returns {node, setActive}.
   * @param {Array} items [{key, label, icon?}]
   * @param {Function} onChange(key)
   */
  function tabs(items, onChange) {
    var bar = el('div', { class: 'tab-bar no-ink', role: 'tablist' });
    var ink = el('span', { class: 'tab-ink', 'aria-hidden': 'true' });
    var activeKey = items.length ? items[0].key : null;

    items.forEach(function (item) {
      bar.appendChild(el('button', {
        class: 'tab-btn', type: 'button', role: 'tab',
        dataset: { tabKey: item.key },
        onclick: function () { if (item.key !== activeKey) { setActive(item.key); onChange(item.key); } }
      }, [
        item.icon ? icon(item.icon, 14) : null,
        el('span', { text: item.label })
      ]));
    });
    bar.appendChild(ink);

    bar.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return;
      var btns = Array.prototype.slice.call(bar.querySelectorAll('.tab-btn'));
      var i = btns.indexOf(document.activeElement);
      if (i === -1) return;
      e.preventDefault();
      var next = e.key === 'Home' ? 0 : e.key === 'End' ? btns.length - 1
               : (i + (e.key === 'ArrowRight' ? 1 : -1) + btns.length) % btns.length;
      btns[next].focus();
      btns[next].click();
    });

    function moveInk() {
      var b = bar.querySelector('.tab-btn.active');
      if (!b || !b.offsetWidth) return;
      ink.style.transform = 'translateX(' + b.offsetLeft + 'px) scaleX(' + (b.offsetWidth / 100) + ')';
    }

    function setActive(key) {
      activeKey = key;
      var btns = bar.querySelectorAll('.tab-btn');
      for (var i = 0; i < btns.length; i++) {
        var on = btns[i].dataset.tabKey === key;
        btns[i].classList.toggle('active', on);
        btns[i].setAttribute('aria-selected', on ? 'true' : 'false');
        btns[i].setAttribute('tabindex', on ? '0' : '-1');
      }
      requestAnimationFrame(moveInk);
    }

    setActive(activeKey);
    // first placement without a slide, then let it glide
    requestAnimationFrame(function () {
      moveInk();
      requestAnimationFrame(function () { bar.classList.remove('no-ink'); });
    });
    if ('ResizeObserver' in window) new ResizeObserver(moveInk).observe(bar);

    return { node: bar, setActive: setActive };
  }

  /* ------------------------------------------------------------------ *
   * Form: a list of field specs -> labelled controls, values out
   * ------------------------------------------------------------------ */

  /**
   * Build a form from specs. Used by the Settings dialogs and, from M2, the
   * request form (admin-defined extra fields use the same kinds).
   *   spec: {key, label, kind, hint, placeholder, unit, mono, required,
   *          options: [{value, label}], showIf(values) -> bool}
   *   kind: text | longtext | number | date | email | password | path |
   *         select | check | checks
   * Returns {node, values(), setError(key, message), clearErrors(), focus()}.
   * values(): numbers as numbers (or null), check -> bool, checks -> [values].
   */
  function form(specs, initial) {
    var init = initial || {};
    var parts = {};
    var node = el('div', { class: 'form-grid' });

    specs.forEach(function (sp) {
      var v = init[sp.key];
      var part;
      if (sp.kind === 'check') {
        var t = toggle({ label: sp.label, checked: !!v });
        part = { node: el('div', { class: 'form-check' }, [t.node, sp.hint ? el('div', { class: 'ifield-msg', text: sp.hint }) : null]),
                 get: function () { return t.input.checked; }, setState: function () {}, input: t.input };
      } else if (sp.kind === 'checks') {
        var boxes = (sp.options || []).map(function (opt) {
          var tb = toggle({ label: opt.label, checked: (v || []).indexOf(opt.value) !== -1 });
          tb.value = opt.value;
          return tb;
        });
        var msg = el('div', { class: 'ifield-msg', 'aria-live': 'polite' }, sp.hint || null);
        var fs = el('fieldset', { class: 'form-checks' }, [
          el('legend', { class: 'ifield-label', text: sp.label }),
          el('div', { class: 'form-checks-row' }, boxes.map(function (b) { return b.node; })),
          msg
        ]);
        part = { node: fs, input: boxes.length ? boxes[0].input : fs,
                 get: function () { return boxes.filter(function (b) { return b.input.checked; }).map(function (b) { return b.value; }); },
                 setState: function (state, message) {
                   fs.classList.toggle('is-invalid', state === 'invalid');
                   clear(msg);
                   if (message) append(msg, [icon('alert', 14), el('span', { text: message })]);
                   else if (sp.hint) msg.textContent = sp.hint;
                 } };
      } else {
        var type = { number: 'number', date: 'date', email: 'email', password: 'password' }[sp.kind] || 'text';
        var f = field({
          label: sp.label, type: type, unit: sp.unit, hint: sp.hint, placeholder: sp.placeholder,
          mono: sp.mono !== undefined ? sp.mono : (sp.kind === 'path' || sp.kind === 'number'),
          multiline: sp.kind === 'longtext', required: !!sp.required, step: sp.kind === 'number' ? 'any' : undefined,
          options: sp.kind === 'select' ? sp.options : undefined,
          list: sp.kind === 'text' && sp.list ? sp.list : undefined,
          combo: sp.kind === 'text' && !!sp.list,
          value: v === null || v === undefined ? (sp.kind === 'select' && sp.options && sp.options[0] ? sp.options[0].value : '') : v
        });
        part = { node: f.node, input: f.input, setState: f.setState,
                 get: function () {
                   var raw = f.value();
                   if (sp.kind === 'number') { var n = String(raw).trim() === '' ? null : Number(raw); return n === null || isFinite(n) ? n : NaN; }
                   return typeof raw === 'string' ? raw.trim() : raw;
                 } };
      }
      if (sp.cls) part.node.classList.add(sp.cls);
      parts[sp.key] = part;
      node.appendChild(part.node);
    });

    function values() {
      var o = {};
      specs.forEach(function (sp) { o[sp.key] = parts[sp.key].get(); });
      return o;
    }
    function applyShowIf() {
      var vals = values();
      specs.forEach(function (sp) { if (sp.showIf) parts[sp.key].node.hidden = !sp.showIf(vals); });
    }
    node.addEventListener('change', applyShowIf);
    node.addEventListener('input', applyShowIf);
    applyShowIf();

    return {
      node: node,
      values: values,
      setError: function (key, message) { if (parts[key]) { parts[key].setState('invalid', message); if (parts[key].input.focus) parts[key].input.focus(); } },
      clearErrors: function () { Object.keys(parts).forEach(function (k) { parts[k].setState(null); }); },
      /** A select's options, replaced (e.g. part numbers of the picked project). */
      setOptions: function (key, options, value) {
        var sel = parts[key] && parts[key].input;
        if (!sel || sel.tagName !== 'SELECT') return;
        clear(sel);
        options.forEach(function (opt) { sel.appendChild(el('option', { value: opt.value, text: opt.label })); });
        sel.value = value !== undefined && value !== null ? String(value) : (options[0] ? String(options[0].value) : '');
      },
      control: function (key) { return parts[key] ? parts[key].input : null; },
      focus: function () { var first = specs.filter(function (sp) { return !parts[sp.key].node.hidden; })[0]; if (first && parts[first.key].input.focus) parts[first.key].input.focus(); }
    };
  }

  ui.form = form;
  ui.button = button;
  ui.combo = comboBox;
  ui.emptyState = emptyState;
  ui.field = field;
  ui.kpiTile = kpiTile;
  ui.panel = panel;
  ui.segmented = segmented;
  ui.skeleton = skeleton;
  ui.tabs = tabs;
  ui.toggle = toggle;
})(window.QVM.ui);
