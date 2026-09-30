# QVM Dashboard - how we work

Vanilla JS port of the Python/Streamlit QVM Manufacturing Dashboard, built on
the `../metrology-request-tracker` shell, UI kit, themes, and test harness.
Decisions: `DECISIONS.md`. Parked items: `OPEN_QUESTIONS.md`.

## Working agreement (with Prince)
- **Plan first.** Before building, ask questions one at a time, give a recommended option, and wait
  for "done" / "got it". Never assume a requirement; unclear → ask. New unknowns go to OPEN_QUESTIONS.md.
- **Small steps.** Build one milestone step at a time; commit each step on the migration branch; Prince reviews.
- **Answers:** short, plain words, a few lines. Always recommend one option and say why.
- **Honesty:** say what was not checked. Never invent data, paths, or values.
- **No browser runs by Claude** (Prince tests in the browser; it saves tokens). Claude runs only
  code-level checks: `node --check` syntax checks on every JS file and the Node test harness
  from M2 (`tests/run-tests.js`, same tests as `tests/test.html`).

## Git rules
- Branch: `qvm-js-migration`. Never commit to main.
- **Author:** Prince Khurana. Never mention Claude or AI in commit messages, branch names or files.
- **Commit messages:** short and plain, the way a person writes them.

## Philosophy (inherited from the tracker)
- **Mission Control look:** dark theme first. All themes live in `js/themes.js`;
  CSS keys only on data-scheme / data-contrast, never a theme name.
- **Purposeful motion:** only `transform`/`opacity` animate; `[data-motion="reduce"]` and
  `prefers-reduced-motion` turn it off.
- **Analyst-only tool.** No identity, no roles, no save-to-folder: uploads live in
  session memory; only tolerances and theme persist (localStorage).

## Hard constraints
- Vanilla JS, classic `<script src>` in dependency order; runs from `file://` in
  Chrome/Edge. No frameworks, no CDN, no npm runtime, no server, no internet.
- Local vendor files only: `vendor/chart.umd.min.js` (Chart.js 4), `vendor/xlsx.full.min.js`
  (SheetJS). Fonts: system stacks; numbers tabular. Icons: inline SVG only. No emojis.
- Safety: user text never reaches `innerHTML` (use `el()`/textContent or `esc()`);
  event delegation via `[data-action]`; no inline `onclick` attributes.

## Layers - who may do what
| Layer | Files | May | May not |
|---|---|---|---|
| Rules & maths | `js/domain.js` | pure functions, unit suffixes (`_um`, `_mm`, `_ppm`), `now_ts` passed in | touch DOM, store, `Date.now()` |
| Views | `js/views/*.js`, `js/app.js` | compose components, call domain | re-implement rules |
| Components | `js/ui/*.js` | build DOM, format, animate | own maths |

## Quality targets (Prince verifies in the browser)
`tests/test.html` all green · `index.html?audit=1` audit clean ·
page render < 150 ms · charts readable in all themes.
Node gates (run all): `run-tests.js`, `sample-check.js`, `ui-smoke.js`
(+`chart` arg), `app-smoke.js`, `dom-budget.js`, `css-check.js`, `contrast.js`.
