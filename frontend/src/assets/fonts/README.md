# Fonts

`figurines.woff2`: the five chess figures ♔ ♕ ♖ ♗ ♘ (U+2654–U+2658) from
[Noto Sans Symbols 2](https://github.com/notofonts/symbols), version 2.008, for moves written
with figurines (♘f3). The whole symbol font is 382 kB; these five glyphs are 5 kB.

Licence: SIL Open Font License 1.1, see `OFL.txt`. Noto declares no Reserved Font Name, so
the cut-down font may keep its name.

How it was made, from the `symbols` subset of `@fontsource/noto-sans-symbols-2` 5.3.0
(`files/noto-sans-symbols-2-symbols-400-normal.woff2`):

```sh
uvx --from 'fonttools[woff]' pyftsubset noto-sans-symbols-2-symbols-400-normal.woff2 \
    --unicodes=U+2654-2658 --flavor=woff2 --output-file=figurines.woff2
```

The serif, Source Serif 4, comes from its npm package instead (see `src/main.tsx` and
`docs/adr/0010-look-and-bundled-fonts.md`).
