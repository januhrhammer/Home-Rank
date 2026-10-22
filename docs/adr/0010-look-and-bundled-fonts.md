# 10. The look: a chess book, with fonts that ship with the app

Date: 2026-10-22

## Status

Accepted. Replaces the "system fonts only" part of [ADR 0005](0005-styling.md).

## Context

Until now the app used a plain baseline look: system fonts, grey surfaces, a blue accent. At the
end of M1 the maintainer chose between three directions, shown on the real pages in light and
dark mode:

1. **Club room**: close to Lichess, with warm greys, a blue accent and a brown board.
2. **Chess book**: moves typeset like an annotated game in print, with figurines, ink-coloured
   text, a bottle-green accent and a blue-grey board like a printed diagram.
3. **Training room**: Atkinson Hyperlegible everywhere, graphite greys, an amber accent.

The brief: light and dark mode, Lichess as a reference, modern, but neither a generic web-app
look nor a web version of SCID or ChessBase.

Directions 2 and 3 need typefaces that most systems don't have. ADR 0005 chose system fonts so
that nothing is downloaded and the app works offline.

## Decision

- **Direction 2, the chess book.** Headings and the move list use a serif; buttons, forms, tables
  and navigation stay in the system's sans-serif. Moves are shown with figurines (♘f3) by
  default; letters (Nf3) remain a setting.
- **Fonts ship with the app.** They are npm packages (Fontsource) or files in the repository,
  bundled by Vite and served by the app itself like any other static file. Nothing is loaded
  from Google Fonts or another third party, so the app still works offline and tells no one
  which pages are open.
  - **Source Serif 4** (SIL Open Font License), weight axis only, as
    `@fontsource-variable/source-serif-4`. Browsers fetch only the subsets a page needs, about
    50 kB each for upright and italic Latin.
  - **Figurines**: the five chess figures from Noto Sans Symbols 2 (SIL Open Font License),
    subset to a few kilobytes and committed with their licence. The full symbol font would be
    382 kB for five glyphs.
- Colours, including the board's, are design tokens in `src/styles/global.css`, with a light and
  a dark set.

## Consequences

- The first visit downloads about 100 kB of fonts; later visits use the browser cache. Until a
  font has arrived, text shows in a fallback serif (`font-display: swap`).
- The Docker image grows by every subset Fontsource provides (about 370 kB), although browsers
  only fetch what they need.
- Both fonts are under the SIL Open Font License, which allows bundling them with AGPL software.
- Changing the look later means changing tokens, not components.
