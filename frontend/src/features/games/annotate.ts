/**
 * Annotating a game: comments, move and position marks, and variations, never the main line's
 * moves (ADR 0019). Each function takes the game's PGN and returns the annotated PGN, which
 * the server checks and saves. Moves are found by their path (see MoveNode.path).
 */
import type { Position } from "chessops/chess";
import {
  ChildNode,
  type Game,
  isChildNode,
  makeComment,
  makePgn,
  type Node,
  parseComment,
  parsePgn,
  type PgnNodeData,
  startingPosition,
} from "chessops/pgn";
import { makeSan, parseSan } from "chessops/san";
import { parseUci } from "chessops/util";

/** Marks for a move, as NAGs ($1 …): one at a time. */
export const MOVE_MARKS = [1, 2, 5, 6, 3, 4]; // !, ?, !?, ?!, !!, ??
/** Marks for the position after a move: one at a time. */
export const POSITION_MARKS = [10, 14, 15, 16, 17, 18, 19]; // =, ⩲, ⩱, ±, ∓, +−, −+

function read(pgn: string): Game<PgnNodeData> {
  const [game] = parsePgn(pgn);
  if (game === undefined) {
    throw new Error("not a game");
  }
  return game;
}

/** The node at `path` ([] for the start), and the position after its move. */
function find(
  game: Game<PgnNodeData>,
  path: number[],
): { node: Node<PgnNodeData>; position: Position } {
  const position = startingPosition(game.headers).unwrap();
  let node: Node<PgnNodeData> = game.moves;
  for (const index of path) {
    const child = node.children[index];
    const move = child && parseSan(position, child.data.san);
    if (child === undefined || move === undefined) {
      throw new Error(`no move at ${path.join(".")}`);
    }
    position.play(move);
    node = child;
  }
  return { node, position };
}

function childAt(game: Game<PgnNodeData>, path: number[]): ChildNode<PgnNodeData> {
  const { node } = find(game, path);
  if (!isChildNode(node)) {
    throw new Error("the start has no move");
  }
  return node;
}

/** The text after a move; its commands ([%clk …], arrows) stay. An empty text removes it. */
export function setComment(pgn: string, path: number[], text: string): string {
  const game = read(pgn);
  const node = childAt(game, path);
  const parsed = (node.data.comments ?? []).map(parseComment);
  const kept = parsed.find((comment) => comment.clock !== undefined || comment.shapes.length > 0);
  const comment = makeComment({ ...kept, text: text.trim() });
  node.data.comments = comment === "" ? [] : [comment];
  return makePgn(game);
}

/** Put a mark on a move, replacing another of its kind; the same mark again removes it. */
export function toggleMark(pgn: string, path: number[], nag: number): string {
  const game = read(pgn);
  const node = childAt(game, path);
  const group = MOVE_MARKS.includes(nag) ? MOVE_MARKS : POSITION_MARKS;
  const nags = node.data.nags ?? [];
  node.data.nags = nags.includes(nag)
    ? nags.filter((other) => other !== nag)
    : [...nags.filter((other) => !group.includes(other)), nag];
  return makePgn(game);
}

/**
 * Play moves (UCI) after the move at `path` (or from the start with []): each follows the line
 * already there if it has the move, else becomes a new variation. The PGN and the path of the
 * last move.
 */
export function addMoves(
  pgn: string,
  path: number[],
  moves: string[],
): { pgn: string; path: number[] } {
  const game = read(pgn);
  const found = find(game, path);
  const { position } = found;
  let node = found.node;
  const newPath = [...path];
  for (const uci of moves) {
    const move = parseUci(uci);
    if (move === undefined || !position.isLegal(move)) {
      throw new Error(`illegal move ${uci}`);
    }
    const san = makeSan(position, move);
    let index = node.children.findIndex((child) => child.data.san === san);
    if (index === -1) {
      node.children.push(new ChildNode<PgnNodeData>({ san }));
      index = node.children.length - 1;
    }
    const next = node.children[index];
    if (next === undefined) {
      throw new Error("lost the move just added");
    }
    position.play(move);
    newPath.push(index);
    node = next;
  }
  return { pgn: makePgn(game), path: newPath };
}

/** Whether a move is the game's own: then it can't be deleted (ADR 0019). */
export function isMainLine(path: number[]): boolean {
  return path.every((index) => index === 0);
}

/** Where the variation a move belongs to starts: the path of its first move. */
export function variationStart(path: number[]): number[] {
  const branch = path.findLastIndex((index) => index !== 0);
  return path.slice(0, branch + 1);
}

/** Delete the variation the move at `path` belongs to, from its first move on. The game's own
 * moves can't be deleted. */
export function deleteVariation(pgn: string, path: number[]): string {
  if (isMainLine(path)) {
    throw new Error("the game's own moves can't be deleted");
  }
  const start = variationStart(path);
  const game = read(pgn);
  const { node: parent } = find(game, start.slice(0, -1));
  parent.children.splice(start.at(-1) ?? 0, 1);
  return makePgn(game);
}
