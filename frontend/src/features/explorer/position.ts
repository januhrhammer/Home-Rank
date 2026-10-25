/**
 * Setting up a position to search for: pieces put on and taken off squares, and the board
 * completed to a full FEN. Pure functions over chessops, testable without a board.
 */
import { Chess } from "chessops/chess";
import { makeBoardFen, parseBoardFen, parseFen } from "chessops/fen";
import type { Piece, Role } from "chessops/types";
import { parseSquare, parseUci } from "chessops/util";

export const START_BOARD = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
export const EMPTY_BOARD = "8/8/8/8/8/8/8/8";

/** The board (pieces only) with a piece put on a square, or the square emptied (null). */
export function putPiece(boardFen: string, square: string, piece: Piece | null): string {
  const board = parseBoardFen(boardFen).unwrap();
  const index = parseSquare(square);
  if (index === undefined) {
    return boardFen;
  }
  if (piece === null) {
    board.take(index);
  } else {
    board.set(index, piece);
  }
  return makeBoardFen(board);
}

/**
 * A full FEN for the board: the side to move, castling where king and rook still stand on
 * their squares (a set-up position can't know more), no en passant square.
 */
export function fullFen(boardFen: string, turn: "white" | "black"): string {
  const board = parseBoardFen(boardFen).unwrap();
  const at = (square: string, color: "white" | "black", role: Role) => {
    const piece = board.get(parseSquare(square) ?? 0);
    return piece?.color === color && piece.role === role;
  };
  const castling = [
    at("e1", "white", "king") && at("h1", "white", "rook") ? "K" : "",
    at("e1", "white", "king") && at("a1", "white", "rook") ? "Q" : "",
    at("e8", "black", "king") && at("h8", "black", "rook") ? "k" : "",
    at("e8", "black", "king") && at("a8", "black", "rook") ? "q" : "",
  ].join("");
  return `${boardFen} ${turn === "white" ? "w" : "b"} ${castling || "-"} - 0 1`;
}

/** Whether the FEN is a legal position: one king each, the side not to move not in check, … */
export function isLegalPosition(fen: string): boolean {
  const setup = parseFen(fen);
  return setup.isOk && Chess.fromSetup(setup.value).isOk;
}

/** The board and side to move of a FEN, if it can be read. */
export function readFen(fen: string): { board: string; turn: "white" | "black" } | null {
  const setup = parseFen(fen.trim());
  if (setup.isErr) {
    return null;
  }
  return { board: makeBoardFen(setup.value.board), turn: setup.value.turn };
}

export interface Placement {
  board: string;
  turn: "white" | "black";
}

/** The board after a move (UCI) in a position, and who is to move then; null if it isn't legal. */
export function playMove(fen: string, uci: string): Placement | null {
  const setup = parseFen(fen);
  const move = parseUci(uci);
  if (setup.isErr || move === undefined) {
    return null;
  }
  const position = Chess.fromSetup(setup.value);
  if (position.isErr || !position.value.isLegal(move)) {
    return null;
  }
  position.value.play(move);
  return { board: makeBoardFen(position.value.board), turn: position.value.turn };
}

/**
 * If a piece dragged on the board was a legal move for the side to move, the position after
 * it, with the other side to move: setting up a position move by move works like playing. Null
 * for anything else (a piece put where no move takes it), which stays a set-up change.
 */
export function asMove(fen: string, nextBoard: string): Placement | null {
  const setup = parseFen(fen);
  if (setup.isErr) {
    return null;
  }
  const position = Chess.fromSetup(setup.value);
  if (position.isErr) {
    return null;
  }
  for (const [from, targets] of position.value.allDests()) {
    for (const to of targets) {
      const after = position.value.clone();
      after.play({ from, to, promotion: promotes(position.value, from, to) });
      if (makeBoardFen(after.board) === nextBoard) {
        return { board: nextBoard, turn: after.turn };
      }
    }
  }
  return null;
}

/** A pawn reaching the last rank becomes a queen, as the board shows it when dragged. */
function promotes(position: Chess, from: number, to: number): Role | undefined {
  const rank = Math.floor(to / 8);
  return position.board.get(from)?.role === "pawn" && (rank === 0 || rank === 7)
    ? "queen"
    : undefined;
}
