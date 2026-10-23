/**
 * A repertoire's moves as the tree the editor shows: the same shape as a game's move tree, so
 * the move list can show it like a book.
 *
 * The server keeps each move by the position it is played from (ADR 0016), so a position
 * reached by two move orders has one set of moves. The tree shows them once, under the shorter
 * way there; the other way ends with a note saying where it transposes to.
 */
import { Chess } from "chessops/chess";
import { chessgroundMove } from "chessops/compat";
import { INITIAL_FEN, makeFen, parseFen } from "chessops/fen";
import { parseUci } from "chessops/util";

import { t } from "../../lib/i18n";
import { type MoveNode, moveNumber, type MoveTree } from "../games";
import type { RepertoireMove } from "./repertoire";

/** The repertoire's starting position, with the move counters the server stores it with. */
export const START_FEN = INITIAL_FEN;

export interface RepertoireTree extends MoveTree {
  /** The repertoire's moves, by id: a tree node has its move's id. */
  moves: Map<number, RepertoireMove>;
  /** For each move that leads to a position shown elsewhere: the node where it is shown. */
  transposesTo: Map<number, MoveNode>;
}

/** The moves as a tree, from the starting position; moves that it doesn't reach are left out. */
export function buildRepertoireTree(moves: RepertoireMove[]): RepertoireTree {
  const byPosition = new Map<string, RepertoireMove[]>();
  for (const move of moves) {
    const list = byPosition.get(move.from_position) ?? [];
    list.push(move);
    byPosition.set(move.from_position, list);
  }
  const start = moves.find((move) => move.from_fen === START_FEN)?.from_position;
  const tree: RepertoireTree = {
    startFen: START_FEN,
    firstMoves: [],
    gameComments: [],
    byId: new Map(),
    moves: new Map(moves.map((move) => [move.id, move])),
    transposesTo: new Map(),
  };
  if (start === undefined) {
    return tree;
  }

  // Breadth first, so that each position is shown where it is reached in the fewest moves.
  const shownAt = new Map<string, MoveNode | null>([[start, null]]);
  const queue: { position: string; parent: MoveNode | null }[] = [
    { position: start, parent: null },
  ];
  for (let item = queue.shift(); item !== undefined; item = queue.shift()) {
    const { position, parent } = item;
    for (const move of byPosition.get(position) ?? []) {
      const node = moveNode(move, parent);
      tree.byId.set(node.id, node);
      (parent ? parent.children : tree.firstMoves).push(node);
      const shown = shownAt.get(move.to_position);
      if (shown === undefined) {
        shownAt.set(move.to_position, node);
        queue.push({ position: move.to_position, parent: node });
      } else if (shown !== null) {
        tree.transposesTo.set(node.id, shown);
      }
      // shown === null: back to the starting position, which needs no note.
    }
  }
  for (const [id, shown] of tree.transposesTo) {
    tree.byId.get(id)?.commentsAfter.push(t("repertoire.transposes", { line: lineTo(shown) }));
  }
  return tree;
}

function moveNode(move: RepertoireMove, parent: MoveNode | null): MoveNode {
  const position = Chess.fromSetup(parseFen(move.from_fen).unwrap()).unwrap();
  const played = parseUci(move.move_uci);
  if (played === undefined) {
    throw new Error(`not a move: ${move.move_uci}`);
  }
  position.play(played);
  return {
    id: move.id,
    ply: (parent?.ply ?? 0) + 1,
    san: move.move_san,
    fen: makeFen(position.toSetup()),
    squares: chessgroundMove(played),
    commentsBefore: [],
    commentsAfter: move.comment ? [move.comment] : [],
    symbols: [],
    parent,
    children: [],
  };
}

/** The moves that lead to a node, written as a line: "1. d4 Nf6 2. c4 e6". */
export function lineTo(node: MoveNode, format: (san: string) => string = (san) => san): string {
  const moves: MoveNode[] = [];
  for (let at: MoveNode | null = node; at !== null; at = at.parent) {
    moves.unshift(at);
  }
  return moves
    .map((move, i) => {
      const number = move.ply % 2 === 1 || i === 0 ? `${moveNumber(move)} ` : "";
      return number + format(move.san);
    })
    .join(" ");
}
