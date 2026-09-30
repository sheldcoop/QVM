/**
 * tests/fake-dom.js - dev only, no dependencies.
 *
 * A tiny fake browser for the node smoke tests (ui-smoke.js, app-smoke.js):
 * elements, text, events that bubble, a few selectors, localStorage,
 * location/history, timers you flush by hand. Grown from ABF Tracker's
 * ui-smoke DOM. It is NOT a real browser: layout, CSS and focus rules are
 * not simulated. Prince checks those in Edge.
 *
 *   const { win, doc, flush, tick, storage } = require('./fake-dom')({ ids: ['main', ...], url: 'file:///x/index.html?who=a' });
 *
 * Selectors: tag, #id, .class, [attr], [attr="v"], comma lists; for
 * "a b" only the last part is checked (enough for these tests).
 */
module.exports = function createDom(o) {
  o = o || {};
  const timers = [], rafs = [], intervals = [];
  const storage = {};

  class Node_ {
    constructor() { this.childNodes = []; this.parentNode = null; this.listeners = {}; }
    get children() { return this.childNodes.filter(n => n.nodeType === 1); }
    get firstChild() { return this.childNodes[0] || null; }
    get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
    appendChild(n) { if (n.parentNode) n.parentNode.removeChild(n); n.parentNode = this; this.childNodes.push(n); return n; }
    removeChild(n) { const i = this.childNodes.indexOf(n); if (i < 0) throw new Error('removeChild: not a child'); this.childNodes.splice(i, 1); n.parentNode = null; return n; }
    contains(n) { while (n) { if (n === this) return true; n = n.parentNode; } return false; }
    get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === doc; }
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
    removeEventListener(t, f) { this.listeners[t] = (this.listeners[t] || []).filter(x => x !== f); }
    dispatch(t, ev) {
      ev = Object.assign({ type: t, target: this, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() {} }, ev || {});
      let n = this;
      while (n) { (n.listeners[t] || []).slice().forEach(f => f.call(n, ev)); n = n.parentNode || (n === doc ? win : null); }
      return ev;
    }
    get textContent() { return this.childNodes.map(c => c.textContent).join(''); }
    set textContent(v) { this.childNodes.forEach(c => { c.parentNode = null; }); this.childNodes = []; if (v !== '' && v !== null && v !== undefined) this.appendChild(new Text_(String(v))); }
  }

  class Text_ extends Node_ {
    constructor(t) { super(); this.nodeType = 3; this.data = t; }
    get textContent() { return this.data; }
  }

  function simple(e, s) {
    if (e.nodeType !== 1) return false;
    const m = s.match(/^([a-z0-9-]*)(#[\w-]+)?((?:\.[\w-]+)*)((?:\[[^\]]+\])*)(:[\w-]+(?:\([^)]*\))?)?$/i);
    if (!m) return false;
    if (m[1] && e.tagName.toLowerCase() !== m[1].toLowerCase()) return false;
    if (m[2] && e.attrs.id !== m[2].slice(1)) return false;
    const cls = (m[3] || '').split('.').filter(Boolean);
    if (!cls.every(c => e.classList.contains(c))) return false;
    const attrs = (m[4] || '').match(/\[[^\]]+\]/g) || [];
    for (const a of attrs) {
      const am = a.match(/^\[([\w-]+)(?:="?([^"\]]*)"?)?\]$/);
      if (!am) continue;
      if (am[1] === 'open' && e.tagName === 'DIALOG') { if (!e.open) return false; continue; }
      if (!(am[1] in e.attrs)) return false;
      if (am[2] !== undefined && e.attrs[am[1]] !== am[2]) return false;
    }
    return true;
  }
  function matches(e, sel) {
    return sel.split(',').some(s => { const parts = s.trim().split(/\s+/); return simple(e, parts[parts.length - 1]); });
  }

  class El extends Node_ {
    constructor(tag) {
      super();
      this.nodeType = 1; this.tagName = tag.toUpperCase(); this.attrs = {};
      this.style = { setProperty(k, v) { this[k] = v; } };
      const self = this;
      this.classList = {
        add: (...c) => { const s = self._cls(); c.forEach(x => s.add(x)); self._set(s); },
        remove: (...c) => { const s = self._cls(); c.forEach(x => s.delete(x)); self._set(s); },
        toggle: (c, f) => { const s = self._cls(); const on = f === undefined ? !s.has(c) : !!f; if (on) s.add(c); else s.delete(c); self._set(s); return on; },
        contains: c => self._cls().has(c)
      };
      const dkey = k => 'data-' + String(k).replace(/[A-Z]/g, x => '-' + x.toLowerCase());
      this.dataset = new Proxy({}, {
        set: (t, k, v) => { self.attrs[dkey(k)] = String(v); return true; },
        get: (t, k) => self.attrs[dkey(k)]
      });
      this.value = ''; this.checked = false; this.disabled = false;
    }
    _cls() { return new Set((this.attrs['class'] || '').split(/\s+/).filter(Boolean)); }
    _set(s) { this.attrs['class'] = [...s].join(' '); }
    get className() { return this.attrs['class'] || ''; }
    set className(v) { this.attrs['class'] = v; }
    get id() { return this.attrs.id || ''; }
    set id(v) { this.attrs.id = String(v); }
    get title() { return this.attrs.title || ''; }
    set title(v) { this.attrs.title = String(v); }
    get href() { return this.attrs.href || ''; }
    set href(v) { this.attrs.href = String(v); }
    setAttribute(k, v) {
      this.attrs[k] = String(v);
      if (k === 'value') this.value = String(v);
      if (k === 'checked') this.checked = true;
      if (k === 'disabled') this.disabled = true;
    }
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
    removeAttribute(k) { delete this.attrs[k]; if (k === 'disabled') this.disabled = false; }
    hasAttribute(k) { return k in this.attrs; }
    set innerHTML(v) { this._html = v; this.childNodes = []; }
    get innerHTML() { return this._html || ''; }
    querySelectorAll(sel) { const out = []; const walk = n => n.children.forEach(c => { if (matches(c, sel)) out.push(c); walk(c); }); walk(this); return out; }
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
    closest(sel) { let n = this; while (n && n.nodeType === 1) { if (matches(n, sel)) return n; n = n.parentNode; } return null; }
    focus() { doc.activeElement = this; }
    blur() { if (doc.activeElement === this) doc.activeElement = null; }
    select() {}
    scrollIntoView() {}
    getBoundingClientRect() { return { left: 0, top: 0, right: 10, bottom: 10, width: 10, height: 10 }; }
    get offsetWidth() { return 50; } get offsetHeight() { return 20; } get offsetLeft() { return 5; }
    showModal() { this.open = true; this.attrs.open = ''; }
    close() { this.open = false; delete this.attrs.open; }
    click() { if (!this.disabled) this.dispatch('click'); }
    dispatchEvent(ev) { this.dispatch(ev.type, {}); return true; }
    get hidden() { return 'hidden' in this.attrs; }
    set hidden(v) { if (v) this.attrs.hidden = ''; else delete this.attrs.hidden; }
    get disabledAttr() { return this.disabled; }
  }

  const doc = new El('#document');
  doc.nodeType = 9;
  doc.documentElement = doc.appendChild(new El('html'));
  doc.body = doc.documentElement.appendChild(new El('body'));
  doc.createElement = t => new El(t);
  doc.createElementNS = (ns, t) => new El(t);
  doc.createTextNode = t => new Text_(t);
  doc.getElementById = id => doc.querySelector('#' + id);
  doc.hidden = false;
  doc.execCommand = () => true;
  (o.ids || []).forEach(id => { const e = new El('div'); e.setAttribute('id', id); doc.body.appendChild(e); });

  // location / history for file:///.../index.html?who=...#/lab
  // like a browser: code that sets location.hash fires "hashchange" (after the current task)
  let hashNow = '';
  const loc = { search: '', pathname: '/index.html' };
  Object.defineProperty(loc, 'hash', { enumerable: true, get: () => hashNow, set: v => {
    const next = v === '' || String(v)[0] === '#' ? String(v) : '#' + v;
    if (next === hashNow) return;
    hashNow = next;
    timers.push(() => (win.listeners.hashchange || []).forEach(f => f({})));
  } });
  function setUrl(u) {
    const m = String(u).match(/^[^?#]*?([^/?#]*\/?[^?#]*)?(\?[^#]*)?(#.*)?$/);
    loc.search = (m && m[2]) || ''; hashNow = (m && m[3]) || '';
  }
  if (o.url) setUrl(o.url);
  const history = { replaceState(s, t, u) { if (u !== undefined) { const i = String(u).indexOf('#'); const q = String(u).indexOf('?'); loc.search = q !== -1 ? String(u).slice(q, i === -1 ? undefined : i) : ''; hashNow = i !== -1 ? String(u).slice(i) : ''; } } };

  const win = {
    document: doc, console, Math, JSON, Date, Intl, Object, Array, String, Number, Promise, Proxy, Set, Map, RegExp, Error,
    parseFloat, parseInt, isFinite, isNaN, encodeURIComponent, decodeURIComponent, URLSearchParams, TextEncoder,
    Uint8Array, Uint32Array, Blob: class { constructor(p) { this.parts = p; } },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
    crypto: globalThis.crypto,
    location: loc, history,
    navigator: { clipboard: { text: null, writeText(t) { this.text = String(t); return Promise.resolve(); } } },
    matchMedia: () => ({ matches: false }),
    IntersectionObserver: class { observe() {} unobserve() {} },
    ResizeObserver: class { observe() {} },
    requestAnimationFrame: f => { rafs.push(f); return rafs.length; },
    setTimeout: (f, ms) => { timers.push(f); return timers.length; }, clearTimeout() {},
    setInterval: f => { intervals.push(f); return intervals.length; }, clearInterval() {},
    getComputedStyle: () => ({ color: 'rgb(10, 20, 30)', getPropertyValue: () => ' x ' }),
    localStorage: { getItem: k => (k in storage ? storage[k] : null), setItem: (k, v) => { storage[k] = String(v); }, removeItem: k => { delete storage[k]; } },
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    Event: class { constructor(type) { this.type = type; } },
    performance: { now: () => Date.now() },
    innerWidth: 1920, innerHeight: 1080,
    listeners: {},
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    removeEventListener() {},
    dispatchEvent(ev) { (this.listeners[ev.type] || []).forEach(f => f(ev)); return true; },
    setHash(h) { hashNow = h; (this.listeners.hashchange || []).forEach(f => f({})); }
  };
  win.window = win;

  /** Run pending animation frames and timeouts (a few rounds). */
  function flush() {
    for (let i = 0; i < 5; i++) {
      const r = rafs.splice(0); r.forEach(f => f(16 * i));
      const t = timers.splice(0); t.forEach(f => f());
    }
  }
  /** Fire every setInterval callback once (the 1 s ticker, the revision poll). */
  function tick() { intervals.forEach(f => f()); }

  return { win, doc, flush, tick, storage, El };
};
