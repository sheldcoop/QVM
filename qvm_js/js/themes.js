/**
 * Metrology Request Tracker - themes.js  (THE one place for themes)
 *
 * Every theme of the app lives in the THEMES list below: its name, mood,
 * the four swatches the picker shows, and its colour tokens. Nothing else
 * defines colours per theme - css/app.css only USES the tokens (var(--bg)
 * ...), and switches a few structural details on the theme's scheme:
 *   [data-scheme="dark"|"light"]   glows or crisp lines
 *   [data-contrast="high"]         2px ink, bigger focus ring
 * The user menu's theme gallery, Settings > Look (the default theme for
 * everyone), ui-kit.html and tests/contrast.js all read this list.
 *
 * The themes (2026-09-28, Prince): our own six - AT&S (the default, company
 * identity), Deep Lab, Cleanroom, Signal, Frost and Minimal. The 2026-09-25
 * set (Carbon Gray 100, Carbon White, Primer High Contrast, Catppuccin Mocha,
 * Gruvbox Light) is retired; its keys map onto these (ALIASES), so nobody's
 * saved choice breaks. Status tokens keep OK / Warning / Line stop / Late
 * clearly apart and readable in every theme.
 *
 * Add a theme: add an entry with a unique key and a group (Main / Personal),
 * run node tests/contrast.js (WCAG AA for every text colour, and the status
 * colours clearly apart).
 *
 * Loaded in <head>, before anything is drawn: install() writes the tokens
 * as a <style> and puts the last used theme on <html> (no flash of the
 * wrong theme). Fonts stay the system stacks (Segoe UI, Cascadia Mono) in
 * every theme - no downloads from file://.
 */
window.QVM = window.QVM || {};
window.QVM.themes = (function () {
  'use strict';

  var DEFAULT = 'ats';
  /** Keys of the retired themes (2026-09-28) -> today's, so a saved choice keeps working. */
  var ALIASES = { dark: 'deep-lab', ocean: 'deep-lab', galaxy: 'deep-lab', forest: 'deep-lab', tech: 'deep-lab',
                  'carbon-g100': 'deep-lab', 'catppuccin-mocha': 'deep-lab',
                  light: 'cleanroom', arctic: 'cleanroom', golden: 'cleanroom', rose: 'cleanroom',
                  'carbon-white': 'cleanroom', 'gruvbox-light': 'cleanroom',
                  hc: 'signal', 'primer-hc': 'signal' };
  var LAST_KEY = 'qvm.theme.last';

  /* Status colours per scheme: the meaning never changes, only the shade that reads well. */
  var STATUS = {
    dark: {
      ok: '#22C55E', 'ok-fg': '#4ADE80', 'ok-bg': 'rgba(34, 197, 94, .12)',
      warning: '#F59E0B', 'warning-fg': '#FBBF24', 'warning-bg': 'rgba(245, 158, 11, .12)',
      critical: '#F97316', 'critical-fg': '#FB9A55', 'critical-bg': 'rgba(249, 115, 22, .13)',
      expired: '#EF4444', 'expired-fg': '#F87171', 'expired-bg': 'rgba(239, 68, 68, .14)',
      blocked: '#64748B', 'blocked-fg': '#A3B1C4', 'blocked-bg': 'rgba(100, 116, 139, .18)',
      danger: '#EF4444', 'danger-fg': '#F87171', 'danger-bg': 'rgba(239, 68, 68, .13)',
      'on-danger': '#1A0606',
      'c-blue': '#93C5FD', 'c-teal': '#2DD4BF', 'c-pink': '#F472B6'
    },
    light: {
      ok: '#15803D', 'ok-fg': '#14612F', 'ok-bg': '#E8F3EC',
      warning: '#C26A00', 'warning-fg': '#8A4A00', 'warning-bg': '#FBF1E2',
      critical: '#D9510C', 'critical-fg': '#9C3706', 'critical-bg': '#FCEDE4',
      expired: '#C81E1E', 'expired-fg': '#991515', 'expired-bg': '#FBE9E9',
      blocked: '#64707E', 'blocked-fg': '#46505C', 'blocked-bg': '#EDEFF2',
      danger: '#C81E1E', 'danger-fg': '#991515', 'danger-bg': '#FBE9E9',
      'on-danger': '#FFFFFF',
      'c-blue': '#1D4ED8', 'c-teal': '#0F766E', 'c-pink': '#BE185D'
    }
  };

  /**
   * The themes. p = the palette: bg, surface, surface-2, surface-3, inset (field well), fg,
   * fg-muted, fg-faint, accent (actions, links, focus), accent-fg (text on accent), and for
   * light themes line / line-strong (solid). Dark themes draw their lines from the accent
   * (or p.ink). Anything else can be set by name in p and wins.
   */
  var THEMES = [

    { key: 'deep-lab', name: 'Deep Lab', scheme: 'dark', group: 'Main',
      mood: 'Dark glass Mission Control: deep navy surfaces, glowing chrome, cool blue accent.',
      swatches: ['#0B1220', '#1A2540', '#57A8F5', '#EAF0FA'],
      p: { bg: '#0B1220', surface: '#111A2C', 'surface-2': '#1A2540', 'surface-3': '#24345A', inset: '#0B1220',
           fg: '#EAF0FA', 'fg-muted': '#B9C4D8', 'fg-faint': '#93A1BB',
           line: '#2A3A5C', 'line-strong': '#3E537F', 'line-hi': '#5EB1FF', bracket: '#3E537F',
           accent: '#57A8F5', 'accent-fill': '#1663CC', 'accent-fg': '#FFFFFF', 'accent-soft': '#12294D',
           'accent-glow': '0 0 0 1px #5EB1FF', 'glow-ring': '100%', 'glow-blur': '0%',
           ok: '#42BE65', 'ok-fg': '#42BE65', 'ok-bg': '#022D0D',
           warning: '#F1C21B', 'warning-fg': '#F1C21B', 'warning-bg': '#302400',
           critical: '#FF832B', 'critical-fg': '#FF832B', 'critical-bg': '#3E1A00',
           expired: '#FA4D56', 'expired-fg': '#FF8389', 'expired-bg': '#520408',
           danger: '#DA1E28', 'danger-fg': '#FF8389', 'danger-bg': '#520408', 'on-danger': '#FFFFFF',
           blocked: '#6F6F6F', 'blocked-fg': '#C6C6C6', 'blocked-bg': '#393939',
           'c-blue': '#78A9FF', 'c-teal': '#08BDBA', 'c-pink': '#FF7EB6',
           radius: '8px', 'radius-panel': '14px',
           shadow: '0 12px 32px rgba(0, 0, 0, .5)', 'shadow-pop': '0 18px 50px rgba(0, 0, 0, .6)', scrim: 'rgba(4, 8, 18, .66)' } },
    { key: 'cleanroom', name: 'Cleanroom', scheme: 'light', group: 'Main',
      mood: 'Light and airy: white room, hairlines, crisp blue, room to breathe.',
      swatches: ['#EDF0F5', '#FFFFFF', '#0F62FE', '#101828'],
      p: { bg: '#EDF0F5', surface: '#FFFFFF', 'surface-2': '#FFFFFF', 'surface-3': '#E7EBF2', inset: '#F4F6FA',
           fg: '#101828', 'fg-muted': '#475467', 'fg-faint': '#556074',
           line: '#D9DFE8', 'line-strong': '#B6BFCF', 'line-hi': '#0F62FE', bracket: '#B6BFCF',
           accent: '#0F62FE', 'accent-fill': '#0F62FE', 'accent-fg': '#FFFFFF', 'accent-soft': '#E3EDFF',
           'accent-glow': '0 0 0 1px #0F62FE',
           ok: '#24A148', 'ok-fg': '#0E6027', 'ok-bg': '#DEFBE6',
           warning: '#F1C21B', 'warning-fg': '#684E00', 'warning-bg': '#FCF4D6',
           critical: '#FF832B', 'critical-fg': '#BA4E00', 'critical-bg': '#FFF2E8',
           expired: '#DA1E28', 'expired-fg': '#A2191F', 'expired-bg': '#FFF1F1',
           danger: '#DA1E28', 'danger-fg': '#A2191F', 'danger-bg': '#FFF1F1', 'on-danger': '#FFFFFF',
           blocked: '#8D8D8D', 'blocked-fg': '#525252', 'blocked-bg': '#E0E0E0',
           'c-blue': '#0043CE', 'c-teal': '#007D79', 'c-pink': '#D02670',
           radius: '10px', 'radius-panel': '16px',
           shadow: '0 1px 2px rgba(16, 24, 40, .06), 0 8px 24px rgba(16, 24, 40, .08)',
           'shadow-pop': '0 4px 8px rgba(16, 24, 40, .08), 0 16px 40px rgba(16, 24, 40, .16)', scrim: 'rgba(16, 24, 40, .45)' } },
    { key: 'signal', name: 'Signal', scheme: 'dark', group: 'Main', contrast: 'high',
      mood: 'Dark, solid, lamp-forward: opaque surfaces, strong borders, amber accent, big numerals.',
      swatches: ['#05070C', '#131A26', '#FFB224', '#FFFFFF'],
      p: { bg: '#05070C', surface: '#0C1119', 'surface-2': '#131A26', 'surface-3': '#1B2434', inset: '#05070C',
           fg: '#FFFFFF', 'fg-muted': '#C3CAD6', 'fg-faint': '#9AA3B5',
           line: '#3A4356', 'line-strong': '#8B94A7', 'line-hi': '#FFB224', bracket: '#8B94A7',
           accent: '#FFB224', 'accent-fill': '#FFB224', 'accent-fg': '#231300', 'accent-soft': '#2A2111',
           'accent-glow': '0 0 0 2px #FFB224', 'glow-ring': '100%', 'glow-blur': '0%', 'focus-w': '3px',
           ok: '#42BE65', 'ok-fg': '#42BE65', 'ok-bg': '#022D0D',
           warning: '#F1C21B', 'warning-fg': '#F1C21B', 'warning-bg': '#302400',
           critical: '#FF832B', 'critical-fg': '#FF832B', 'critical-bg': '#3E1A00',
           expired: '#FA4D56', 'expired-fg': '#FF8389', 'expired-bg': '#520408',
           danger: '#DA1E28', 'danger-fg': '#FF8389', 'danger-bg': '#520408', 'on-danger': '#FFFFFF',
           blocked: '#6F6F6F', 'blocked-fg': '#C6C6C6', 'blocked-bg': '#393939',
           'c-blue': '#78A9FF', 'c-teal': '#08BDBA', 'c-pink': '#FF7EB6',
           radius: '4px', 'radius-panel': '6px',
           shadow: '0 0 0 1px #000000, 0 10px 28px rgba(0, 0, 0, .55)',
           'shadow-pop': '0 0 0 1px #8B94A7, 0 16px 44px rgba(0, 0, 0, .65)', scrim: 'rgba(3, 5, 9, .8)' } },
    { key: 'frost', name: 'Frost', scheme: 'light', group: 'Main',
      mood: 'Glass flagship, Apple-minimalist: restraint, whitespace, frosted chrome, one blue, quiet type.',
      swatches: ['#F5F5F7', '#FFFFFF', '#006DCE', '#1D1D1F'],
      p: { bg: '#F5F5F7', surface: '#FFFFFF', 'surface-2': '#FFFFFF', 'surface-3': '#ECECF0', inset: '#F5F5F7',
           fg: '#1D1D1F', 'fg-muted': '#515154', 'fg-faint': '#636366',
           line: '#E5E5EA', 'line-strong': '#C7C7CC', 'line-hi': '#006DCE', bracket: '#C7C7CC',
           accent: '#006DCE', 'accent-fill': '#006DCE', 'accent-fg': '#FFFFFF', 'accent-soft': '#E8F1FC',
           'accent-glow': '0 0 0 3px rgba(0, 109, 206, .25)',
           ok: '#24A148', 'ok-fg': '#0E6027', 'ok-bg': '#DEFBE6',
           warning: '#F1C21B', 'warning-fg': '#684E00', 'warning-bg': '#FCF4D6',
           critical: '#FF832B', 'critical-fg': '#BA4E00', 'critical-bg': '#FFF2E8',
           expired: '#DA1E28', 'expired-fg': '#A2191F', 'expired-bg': '#FFF1F1',
           danger: '#DA1E28', 'danger-fg': '#A2191F', 'danger-bg': '#FFF1F1', 'on-danger': '#FFFFFF',
           blocked: '#8D8D8D', 'blocked-fg': '#525252', 'blocked-bg': '#E0E0E0',
           'c-blue': '#0043CE', 'c-teal': '#007D79', 'c-pink': '#D02670',
           radius: '12px', 'radius-panel': '20px',
           shadow: '0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .08)',
           'shadow-pop': '0 8px 16px rgba(0, 0, 0, .08), 0 24px 64px rgba(0, 0, 0, .16)', scrim: 'rgba(245, 245, 247, .6)' } },
    { key: 'ats', name: 'AT&S', scheme: 'light', group: 'Main',
      mood: 'Company identity: deep navy on a white room; corporate red only where it hurts (late, danger).',
      swatches: ['#EDF1F6', '#FFFFFF', '#003366', '#CC0000'],
      p: { bg: '#EDF1F6', surface: '#FFFFFF', 'surface-2': '#FFFFFF', 'surface-3': '#DCE4EE', inset: '#F7F9FC',
           fg: '#0B1B30', 'fg-muted': '#34465E', 'fg-faint': '#55677F',
           line: '#C9D4E2', 'line-strong': '#93A5BB', 'line-hi': '#003366', bracket: '#93A5BB',
           accent: '#003366', 'accent-fill': '#003366', 'accent-fg': '#FFFFFF', 'accent-soft': '#D9E4F2',
           'accent-glow': '0 0 0 1px #003366',
           ok: '#24A148', 'ok-fg': '#0E6027', 'ok-bg': '#DEFBE6',
           warning: '#F1C21B', 'warning-fg': '#684E00', 'warning-bg': '#FCF4D6',
           critical: '#FF832B', 'critical-fg': '#BA4E00', 'critical-bg': '#FFF2E8',
           expired: '#CC0000', 'expired-fg': '#8F0000', 'expired-bg': '#FBE9E9',
           danger: '#CC0000', 'danger-fg': '#8F0000', 'danger-bg': '#FBE9E9', 'on-danger': '#FFFFFF',
           blocked: '#8D8D8D', 'blocked-fg': '#525252', 'blocked-bg': '#E0E0E0',
           'c-blue': '#003366', 'c-teal': '#007D79', 'c-pink': '#D02670',
           radius: '6px', 'radius-panel': '10px',
           shadow: '0 1px 2px rgba(11, 27, 48, .08), 0 8px 24px rgba(11, 27, 48, .1)',
           'shadow-pop': '0 8px 24px rgba(11, 27, 48, .18)', scrim: 'rgba(11, 27, 48, .45)' } },
    { key: 'minimal', name: 'Minimal', scheme: 'light', group: 'Main',
      mood: 'Strictly monochrome - black, white, grays, no decoration. Only the status colors keep their standard hues, so meaning never depends on shade alone.',
      swatches: ['#FAFAFA', '#FFFFFF', '#111111', '#000000'],
      p: { bg: '#FAFAFA', surface: '#FFFFFF', 'surface-2': '#FFFFFF', 'surface-3': '#F0F0F0', inset: '#FAFAFA',
           fg: '#111111', 'fg-muted': '#525252', 'fg-faint': '#6E6E6E',
           line: '#E0E0E0', 'line-strong': '#A8A8A8', 'line-hi': '#111111', bracket: '#A8A8A8',
           accent: '#111111', 'accent-fill': '#111111', 'accent-fg': '#FFFFFF', 'accent-soft': '#ECECEC',
           'accent-glow': '0 0 0 1px #111111',
           ok: '#24A148', 'ok-fg': '#0E6027', 'ok-bg': '#DEFBE6',
           warning: '#F1C21B', 'warning-fg': '#684E00', 'warning-bg': '#FCF4D6',
           critical: '#FF832B', 'critical-fg': '#BA4E00', 'critical-bg': '#FFF2E8',
           expired: '#DA1E28', 'expired-fg': '#A2191F', 'expired-bg': '#FFF1F1',
           danger: '#DA1E28', 'danger-fg': '#A2191F', 'danger-bg': '#FFF1F1', 'on-danger': '#FFFFFF',
           blocked: '#8D8D8D', 'blocked-fg': '#525252', 'blocked-bg': '#E0E0E0',
           'c-blue': '#404040', 'c-teal': '#595959', 'c-pink': '#737373',
           radius: '6px', 'radius-panel': '8px',
           shadow: '0 1px 3px rgba(0, 0, 0, .12)', 'shadow-pop': '0 8px 24px rgba(0, 0, 0, .18)', scrim: 'rgba(0, 0, 0, .4)' } },
  ];

  function rgb(hex) {
    var n = parseInt(hex.slice(1), 16);
    return [n >> 16, n >> 8 & 255, n & 255].join(', ');
  }

  /** Every token of a theme, as {name: value} (names without the leading --). */
  function tokens(t) {
    var p = t.p, dark = t.scheme === 'dark', o = {};
    var s = STATUS[t.scheme];
    Object.keys(s).forEach(function (k) { o[k] = s[k]; });
    ['bg', 'surface', 'surface-2', 'surface-3', 'inset', 'fg', 'fg-muted', 'fg-faint', 'accent', 'accent-fg'].forEach(function (k) { o[k] = p[k]; });
    var a = rgb(p.accent), ink = rgb(p.ink || p.accent);
    if (dark) {
      o['grid-line'] = t.grid ? 'rgba(' + ink + ', .045)' : 'transparent';
      o.line = 'rgba(' + ink + ', .15)';
      o['line-strong'] = 'rgba(' + ink + ', .28)';
      o['line-hi'] = 'rgba(' + ink + ', .5)';
      o.bracket = 'rgba(' + ink + ', .55)';
      o['accent-soft'] = 'rgba(' + a + ', .12)';
      o['accent-glow'] = '0 0 0 1px rgba(' + a + ', .5), 0 0 18px rgba(' + a + ', .28)';
      o['glow-ring'] = '40%'; o['glow-blur'] = '32%';
      o.shadow = '0 1px 0 rgba(255, 255, 255, .03) inset, 0 10px 28px rgba(0, 0, 0, .38)';
      o['shadow-pop'] = '0 18px 48px rgba(0, 0, 0, .55)';
      o.scrim = 'rgba(3, 6, 10, .6)';
    } else {
      o['grid-line'] = 'transparent';
      o['line-hi'] = p.accent;
      o.bracket = p['line-strong'];
      o['accent-soft'] = 'rgba(' + a + ', .08)';
      o['accent-glow'] = '0 0 0 1px ' + p.accent;
      o['glow-ring'] = '100%'; o['glow-blur'] = '0%';
      var f = rgb(p.fg);
      o.shadow = '0 1px 0 rgba(' + f + ', .05)';
      o['shadow-pop'] = '0 12px 32px rgba(' + f + ', .18)';
      o.scrim = 'rgba(' + f + ', .35)';
    }
    o['accent-fill'] = p.accent;           // buttons and other filled accents; a theme can set its own (Carbon dark)
    Object.keys(p).forEach(function (k) { if (k !== 'ink') o[k] = p[k]; });    // the theme's own values win
    return o;
  }

  /** The CSS of all themes: one [data-theme="key"] block each, the default's block
      FIRST (it also sits on :root, and :root ties every [data-theme] block on
      specificity - so the default must come first or it would paint over every
      theme the page picks). The rest follow in gallery order. */
  function css() {
    var ordered = THEMES.filter(function (t) { return t.key === DEFAULT; })
      .concat(THEMES.filter(function (t) { return t.key !== DEFAULT; }));
    return ordered.map(function (t) {
      var o = tokens(t);
      var sel = (t.key === DEFAULT ? ':root, ' : '') + '[data-theme="' + t.key + '"]';
      return sel + ' {\n  color-scheme: ' + t.scheme + ';\n' + Object.keys(o).map(function (k) { return '  --' + k + ': ' + o[k] + ';'; }).join('\n') + '\n}';
    }).join('\n');
  }

  function byKey(key) { key = ALIASES[key] || key; return THEMES.filter(function (t) { return t.key === key; })[0] || null; }

  /** The attributes that put a theme on an element (the page, or a ui-kit sample). */
  function attrs(key) {
    var t = byKey(key) || byKey(DEFAULT);   // an old key resolves through ALIASES
    return { 'data-theme': t.key, 'data-scheme': t.scheme, 'data-contrast': t.contrast || 'normal' };
  }

  function setOn(elm, key) {
    var a = attrs(key);
    Object.keys(a).forEach(function (k) { elm.setAttribute(k, a[k]); });
    return a['data-theme'];
  }

  /** Put a theme on the page; remembered as "last used" on this PC for the next start. */
  function apply(key) {
    var k = setOn(document.documentElement, key);
    try { localStorage.setItem(LAST_KEY, k); } catch (e) { /* private mode */ }
    return k;
  }

  /** Write the tokens once and show the last used theme before anything is drawn. */
  function install() {
    if (typeof document === 'undefined' || document.getElementById('qvm-themes')) return;
    var st = document.createElement('style');
    st.id = 'qvm-themes';
    st.textContent = css();
    (document.head || document.documentElement).appendChild(st);
    var last = null;
    try { last = localStorage.getItem(LAST_KEY); } catch (e) { /* private mode */ }
    setOn(document.documentElement, byKey(last) ? last : (document.documentElement.getAttribute('data-theme') || DEFAULT));
  }

  install();

  return { list: THEMES, DEFAULT: DEFAULT, byKey: byKey, tokens: tokens, css: css, attrs: attrs, setOn: setOn, apply: apply, install: install };
})();
