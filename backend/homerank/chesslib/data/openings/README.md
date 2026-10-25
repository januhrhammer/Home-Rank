# Opening names

`a.tsv` to `e.tsv` are Lichess's opening list, [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings)
at commit `a6189a30dc273ccb21fc2536a9a2fefd5592a67a`, unchanged. Its authors released it under
the [CC0 1.0 Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/).

Each row is an opening: its ECO code, its English name and its moves from the starting position.
`homerank.chesslib.openings` reads them (ADR 0021). `just openings <commit>` replaces them with
another version of the list; the tests then check that every row can be read.
