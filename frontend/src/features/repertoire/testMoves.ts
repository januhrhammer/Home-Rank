/** Test data: repertoire moves as the API returns them, built from lines of SAN moves. */
import { Chess } from "chessops/chess";
import { INITIAL_FEN, makeFen, parseFen } from "chessops/fen";
import { makeSan, parseSan } from "chessops/san";
import { makeUci } from "chessops/util";

import type { RepertoireMove } from "./repertoire";

/** Stands in for the server's position hash: the FEN without the move counters. */
function positionOf(fen: string): string {
  return fen.split(" ").slice(0, 4).join(" ");
}

/**
 * The moves of the lines, each from the starting position, as the server keeps them: once per
 * position and move, with ids in the order first played. Moves played by White get a card if
 * `color` is "white", and so on.
 */
export function movesOf(
  lines: string[][],
  { color = "white", comments = {} }: { color?: string; comments?: Record<string, string> } = {},
): RepertoireMove[] {
  const moves = new Map<string, RepertoireMove>();
  for (const line of lines) {
    const position = Chess.fromSetup(parseFen(INITIAL_FEN).unwrap()).unwrap();
    for (const san of line) {
      const fen = makeFen(position.toSetup());
      const move = parseSan(position, san);
      if (move === undefined) {
        throw new Error(`illegal move ${san} in ${fen}`);
      }
      const key = `${positionOf(fen)} ${makeUci(move)}`;
      const userToMove = position.turn === color;
      const moveSan = makeSan(position, move);
      position.play(move);
      if (!moves.has(key)) {
        const id = moves.size + 1;
        moves.set(key, {
          id,
          from_position: positionOf(fen),
          from_fen: fen,
          move_uci: makeUci(move),
          move_san: moveSan,
          to_position: positionOf(makeFen(position.toSetup())),
          comment: comments[moveSan] ?? "",
          card_id: userToMove ? 100 + id : null,
        });
      }
    }
  }
  return [...moves.values()];
}
