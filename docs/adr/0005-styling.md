# 5. Styling and accessible components: CSS Modules and React Aria

Date: 2026-10-21

## Status

Accepted. Fonts: replaced by [ADR 0010](0010-look-and-bundled-fonts.md), which bundles them
with the app instead of using the system's own.

## Context

The frontend needs a way to style components and, separately, a source of complex interactive
widgets. Widgets such as dialogs, menus, comboboxes, tables and trees are hard to make accessible
by hand: focus handling, keyboard navigation and screen-reader attributes all have to be right.
Home-Rank requires keyboard use, visible focus and AA contrast, and it must work on phones.

Its core screens (board, move list, evaluation graph, opening explorer) are custom anyway. The
generic parts need, among others, a sortable game table, filters with type-to-search for players
and openings, a date range and a rating range, tags, and a repertoire tree.

The code should stay easy to read, and dependencies few.

Options considered:

1. **Tailwind CSS:** utility classes in the markup; fast to build with, consistent spacing and
   colours, but long class lists in JSX and a vocabulary to learn on top of CSS.
2. **Tailwind with shadcn/ui:** ready-made, accessible components (built on Radix UI) copied into
   the repository. Fastest and polished, but it brings Tailwind, several helper packages and
   dense copied code that we would have to maintain.
3. **CSS Modules with a headless component library:** plain CSS, scoped per component, plus a
   library that supplies behaviour and accessibility but no styling. The candidates were Radix UI
   and React Aria Components.

## Decision

- **CSS Modules** for styling: `Component.module.css` next to each component. Vite scopes the
  class names per file, so they never clash, and no extra dependency is needed.
- **Design tokens** (colours, spacing, radius, fonts) as CSS custom properties in
  `src/styles/global.css`, with a dark theme following the system setting. Components use the
  tokens rather than raw values. System fonts only, so nothing is downloaded.
- **React Aria Components** (Adobe) for complex accessible widgets, added when the first one is
  needed. Unlike Radix it offers a table, combobox, date range picker, number field, tag group
  and tree, which the planned screens need, and it handles internationalisation and touch
  interaction. Its components expose state as data attributes (`[data-selected]`,
  `[data-focus-visible]`), which CSS Modules can style directly.

## Consequences

- Markup stays short; styles are plain CSS that any web developer can read.
- Consistency depends on using the tokens. There is no fixed utility scale enforcing it.
- TypeScript does not catch a misspelled class name: Vite types CSS Modules as "any name is a
  string", so `styles.pgae` silently yields no class. A type generator could fix this, at the
  cost of another tool; not worth it yet.
- React Aria's API is more verbose than Radix's, and there are fewer examples online, since much
  of the community uses Radix through shadcn/ui.
- Colour tokens were checked against WCAG AA: every text colour reaches at least 4.5:1 on both
  backgrounds, in light and dark theme.
