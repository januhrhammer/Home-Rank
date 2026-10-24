/**
 * A game's moves as a tree, ready to show and step through: every move with the position after
 * it, the squares to highlight, and its comments and annotation symbols. Built from the PGN
 * text with chessops, the chess library from Lichess.
 */
import type { SquareName } from "chessops";
import type { Position } from "chessops/chess";
import { chessgroundMove } from "chessops/compat";
import { makeFen } from "chessops/fen";
import {
  type Node,
  parseComment,
  parsePgn,
  type PgnNodeData,
  startingPosition,
} from "chessops/pgn";
import { parseSan } from "chessops/san";

export interface MoveNode {
  id: number;
  /** Where the move is in the PGN's tree: the index among its siblings at each step from the
   * start, e.g. [0, 0, 1] for a variation to Black's first move. All zeros: the main line. */
  path: number[];
  /** Half-moves played up to and including this one: 1 is White's first move. */
  ply: number;
  san: string;
  /** The position after this move. */
  fen: string;
  /** The squares the move went from and to, for highlighting. */
  squares: SquareName[];
  /** Comments before and after the move, without commands such as [%clk 0:03:00]. */
  commentsBefore: string[];
  commentsAfter: string[];
  /** Annotation symbols such as "!" or "±". */
  symbols: string[];
  parent: MoveNode | null;
  /** The moves that can follow: the first continues the line, the others are variations. */
  children: MoveNode[];
}

export interface MoveTree {
  startFen: string;
  /** The candidates for the first move: the game's own, then variations to it. */
  firstMoves: MoveNode[];
  /** Comments on the game as a whole, before the first move. */
  gameComments: string[];
  byId: Map<number, MoveNode>;
}

/** NAGs, the numbered annotations of PGN ($1), as the symbols chess books print. */
export const SYMBOLS: Record<number, string> = {
  1: "!",
  2: "?",
  3: "!!",
  4: "??",
  5: "!?",
  6: "?!",
  7: "□",
  10: "=",
  13: "∞",
  14: "⩲",
  15: "⩱",
  16: "±",
  17: "∓",
  18: "+−",
  19: "−+",
  22: "⨀",
  23: "⨀",
  32: "⟳",
  33: "⟳",
  36: "→",
  37: "→",
  40: "↑",
  41: "↑",
  132: "⇆",
  133: "⇆",
  138: "⊕",
  139: "⊕",
  146: "N",
};

function texts(comments: string[] | undefined): string[] {
  return (comments ?? []).map((comment) => parseComment(comment).text.trim()).filter(Boolean);
}

/** The game's move tree, or null if the PGN text can't be read. */
export function buildMoveTree(pgn: string): MoveTree | null {
  const [game] = parsePgn(pgn);
  if (game === undefined) {
    return null;
  }
  const start = startingPosition(game.headers);
  if (start.isErr) {
    return null;
  }
  const byId = new Map<number, MoveNode>();
  let nextId = 0;

  // Each move is played on a copy of the position before it, so variations branch off cleanly.
  function movesAfter(node: Node<PgnNodeData>, position: Position, parent: MoveNode | null) {
    const moves: MoveNode[] = [];
    for (const [index, child] of node.children.entries()) {
      const after = position.clone();
      const move = parseSan(after, child.data.san);
      if (move === undefined) {
        continue; // an illegal move in a variation: that line ends before it
      }
      after.play(move);
      const moveNode: MoveNode = {
        id: nextId++,
        path: [...(parent?.path ?? []), index],
        ply: (parent?.ply ?? plyOf(position)) + 1,
        san: child.data.san,
        fen: makeFen(after.toSetup()),
        squares: chessgroundMove(move),
        commentsBefore: texts(child.data.startingComments),
        commentsAfter: texts(child.data.comments),
        symbols: (child.data.nags ?? []).flatMap((nag) => SYMBOLS[nag] ?? []),
        parent,
        children: [],
      };
      byId.set(moveNode.id, moveNode);
      moveNode.children = movesAfter(child, after, moveNode);
      moves.push(moveNode);
    }
    return moves;
  }

  const position = start.value;
  return {
    startFen: makeFen(position.toSetup()),
    firstMoves: movesAfter(game.moves, position, null),
    gameComments: texts(game.comments),
    byId,
  };
}

/** Half-moves played before a position, from its move number: 0 at the usual start. */
function plyOf(position: Position): number {
  return (position.fullmoves - 1) * 2 + (position.turn === "white" ? 0 : 1);
}

/** The move's number as written before it: "12." for White, "12…" for Black. */
export function moveNumber(node: MoveNode): string {
  const fullMove = Math.ceil(node.ply / 2);
  return node.ply % 2 === 1 ? `${String(fullMove)}.` : `${String(fullMove)}…`;
}

/** The game's own moves, without variations: the n-th is the position of analysis ply n. */
export function mainLine(tree: MoveTree): MoveNode[] {
  const moves: MoveNode[] = [];
  let next = tree.firstMoves[0];
  while (next !== undefined) {
    moves.push(next);
    next = next.children[0];
  }
  return moves;
}

/** The last move of the line that continues from `node` (or from the start, if null). */
export function endOfLine(tree: MoveTree, node: MoveNode | null): MoveNode | null {
  let current = node ?? tree.firstMoves[0] ?? null;
  while (current?.children[0] !== undefined) {
    current = current.children[0];
  }
  return current;
}

/** The move at `path` (see MoveNode.path), or null for the start or a path that isn't there. */
export function nodeAtPath(tree: MoveTree, path: number[] | null): MoveNode | null {
  let candidates = tree.firstMoves;
  let node: MoveNode | null = null;
  for (const index of path ?? []) {
    node = candidates.find((candidate) => candidate.path.at(-1) === index) ?? null;
    if (node === null) {
      return null;
    }
    candidates = node.children;
  }
  return node;
}
