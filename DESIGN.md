# Market Pulse design system: "the market pages"

The site reads like the market-data section of a financial paper turned into a working tool:
one headline figure, then honest, dense evidence. All three pages (`index.html` Today,
`opportunity.html` Scanner, `weekly.html` Weekly recap) share one stylesheet, `assets/mp.css`,
and one small script, `assets/mp.js` (language and day/night toggles, dateline, direction marks).

## Editions

- **Day edition:** newsprint-peach paper, ink-black text.
- **Night edition:** ink-brown paper, warm cream text.
- The OS setting picks the edition; the masthead button overrides it and remembers the choice
  per device (`localStorage` key `mp-theme`).

## Languages

- **English** and **Hebrew**. The masthead's language button (beside the edition button) names the
  other language in its own script, עברית or English, and remembers the choice per device
  (`localStorage` key `mp-lang`). A `?lang=he` / `?lang=en` link sets it too, and a browser whose
  first language is Hebrew opens in Hebrew. Shared weekly-recap links carry `&lang=he` from a Hebrew page.
- Hebrew pages run right to left (`<html dir="rtl">`, set before first paint). Layout uses logical
  sides (`margin-inline-start`, `text-align: end`), so the whole page mirrors: masthead, tabs, tables,
  grids. Number lines and charts do not mirror: −100 stays left, +100 right, time runs left to right
  (`.ltr` containers; their labels take the direction of their own text).
- Hebrew text keeps signed numbers whole (a left-to-right mark before the sign), never breaks a line
  between a prefix hyphen and its number or Latin word (ב-2.7%, ה-S&P 500), and keeps index names on
  one line (`MP_BIDI` in `mp.js`).
- Weekly price lines move a label down a row when it would collide with its neighbour, in either
  language (`untangle` in `weekly.html`).
- The Hebrew is written, not machine-translated: wording, terms and names follow `docs/hebrew.md`.

## Color tokens (`:root` in `assets/mp.css`)

| Token | Day | Night | Use |
|---|---|---|---|
| `--paper` | `#F5E4D3` | `#17130F` | page ground |
| `--paper-2` | `#EFD8C2` | `#211B16` | boxes |
| `--paper-3` | `#E6C9AE` | `#2D251E` | skeletons, quiet chips |
| `--ink` | `#1E1A16` | `#F3E3D2` | text, heavy rules |
| `--ink-2` | `#57483B` | `#C3AE99` | secondary text |
| `--ink-3` | `#615040` | `#A6927E` | captions, as-of times |
| `--rule` | `#CFB49B` | `#3D3329` | hairlines |
| `--opp` | `#1B4C8C` | `#8BB8F2` | opportunity / up / buy |
| `--cau` | `#8A310E` | `#F29B66` | caution / down / sell |

**Reserved ink.** Blue and vermilion only ever mean opportunity/up/buy and caution/down/sell,
and they always travel with a word or a ▲/▼ mark (`window.MP_MARK`). They are never decorative,
so meaning never depends on hue alone. All text pairs pass WCAG AA (4.5:1) in both editions,
including chips on `--paper-2`.

## Type

- **Source Serif 4:** masthead, headings, the big composite figure and recap headlines.
- **Barlow / Barlow Semi Condensed:** every label, number and data row, with tabular lining figures.
- **Hebrew:** Frank Ruhl Libre (the classic Hebrew newspaper serif) under Source Serif 4, and
  Assistant under Barlow. Their font files hold only Hebrew letters, so Latin text and every digit
  look the same in both languages. All fonts are served from this site.
- Scale: 13 / 16 / 19 / 24 / 32 px, plus one oversized figure per page.

## Structure

- 3px masthead rule, 1px dateline rule, 2px section rules, hairlines between rows.
- Square-ish 2px corners, no shadows, no gradients.
- Tabs **Today / Scanner / Weekly recap** (היום / סורק / סיכום שבועי) sit under the dateline on every
  page (44px touch targets).
- Every reading shows its as-of time. Stale data gets a vermilion **STALE** stamp and a notice;
  it is never silently hidden.
- "Not financial advice" sits in every footer.

## Phones

Phone first: the evening check before the open is the main moment.

- **Section bar:** on the Scanner and Weekly recap, the jump chips become a sticky, swipeable
  bar under 760px. The chip for the section in view is inked (`MP_JUMP` in `mp.js`).
- **Signal scale:** under 560px each signal's track spans the full width, under its name and reading.
- **Weekly recap:** the market strip becomes a two-column grid instead of a sideways scroll, and the
  sector heatmap becomes a ranked bar list from a centre line, both under 640px.
- **Touch:** every control is at least 44px. Hover styles apply only where a pointer can hover, so
  a tapped button never stays inked. Padding respects the notch and the home indicator.

## Signature moment

The five scored signals are plotted as dots on one shared −100…+100 scale under the composite figure,
so every signal is compared on the same axis.

## Weekly recap

The page renders `data/weekly/*.json` editions (see `docs/weekly-recap.md`). Company-insider
rows come automatically from `data/weekly_numbers.json`; the written sections come from each
Sunday's pull request, in English with a Hebrew `he` block. An edition without its Hebrew shows in
English (left to right) on a Hebrew page, under a short Hebrew note.

## Images

`og-image.png` and `icons/icon-192.png` / `icon-512.png` were rendered from HTML using these
same tokens and fonts during the 2026 redesign. Re-render them if the tokens change.
