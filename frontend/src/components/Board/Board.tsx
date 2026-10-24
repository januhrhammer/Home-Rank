import "@lichess-org/chessground/assets/chessground.base.css";
import "@lichess-org/chessground/assets/chessground.cburnett.css";

import { Chessground } from "@lichess-org/chessground";
import type { Api } from "@lichess-org/chessground/api";
import type { Color, Key } from "@lichess-org/chessground/types";
import { useEffect, useRef } from "react";

import { t } from "../../lib/i18n";
import styles from "./Board.module.css";

/** Lets the user move pieces of one colour, to the squares given. */
export interface Movable {
  color: Color;
  /** The legal moves: for each square, where its piece may go. */
  dests: Map<Key, Key[]>;
  onMove: (from: Key, to: Key) => void;
}

export interface BoardProps {
  /** The position in FEN notation. */
  fen: string;
  /** Which side is shown at the bottom. */
  orientation?: Color;
  /** The squares the last move went from and to, highlighted on the board. */
  lastMove?: Key[];
  /** What the board shows, for screen readers, e.g. "Position after 12. Nf3". */
  label?: string;
  /** If given, the user can move; otherwise the board only shows the position. */
  movable?: Movable;
  /**
   * If given, the board is for setting up a position: pieces move freely, a piece dragged off
   * the board is removed, and onChange gets the board's new FEN (pieces only). onSquare is
   * called with a clicked square, e.g. to put a piece there.
   */
  editable?: { onChange: (boardFen: string) => void; onSquare: (square: Key) => void };
  /** Arrows to draw, e.g. the engine's best moves; the best one stands out. */
  arrows?: { from: Key; to: Key; best: boolean }[];
}

/**
 * A chessboard showing one position, on which the user can also move when `movable` says so.
 *
 * The only place in the app that uses chessground. chessground changes the page directly
 * instead of going through React, so the board is created once and then updated via its API.
 */
export function Board({
  fen,
  orientation = "white",
  lastMove,
  label,
  movable,
  editable,
  arrows,
}: BoardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<Api | null>(null);
  // The props of the first render; useRef keeps its initial value for good.
  const initialRef = useRef({ fen, orientation, lastMove });
  // The latest move handler, for chessground's event, which is set up only once.
  const onMoveRef = useRef<Movable["onMove"] | undefined>(undefined);
  const editableRef = useRef<BoardProps["editable"]>(undefined);
  useEffect(() => {
    onMoveRef.current = movable?.onMove;
    editableRef.current = editable;
  });

  // Create the board once, already showing the first position: created empty, chessground
  // would show the starting position and then animate to ours. Remove the board, with its
  // event listeners, when the component goes away.
  useEffect(() => {
    if (containerRef.current === null) {
      return;
    }
    boardRef.current = Chessground(containerRef.current, {
      ...initialRef.current,
      // Pieces glide to their new squares, unless the system asks for less motion.
      animation: { enabled: !window.matchMedia("(prefers-reduced-motion: reduce)").matches },
      movable: {
        free: false,
        showDests: true,
        events: {
          after: (from, to) => {
            onMoveRef.current?.(from, to);
          },
        },
      },
      events: {
        change: () => {
          const board = boardRef.current;
          if (board && editableRef.current) {
            editableRef.current.onChange(board.getFen());
          }
        },
        select: (square) => {
          editableRef.current?.onSquare(square);
        },
      },
    });
    return () => {
      boardRef.current?.destroy();
      boardRef.current = null;
    };
  }, []);

  // Follow later changes; chessground animates the moves (see above). Without `movable` the board takes no
  // moves at all; with it, only the given colour's, to the given squares.
  useEffect(() => {
    boardRef.current?.set({
      fen,
      orientation,
      lastMove,
      turnColor: movable?.color ?? orientation,
      movable: editable
        ? { free: true, color: "both" }
        : { free: false, color: movable?.color, dests: movable?.dests ?? new Map() },
      draggable: {
        enabled: movable !== undefined || editable !== undefined,
        deleteOnDropOff: !!editable,
      },
      selectable: { enabled: movable !== undefined || editable !== undefined },
    });
  }, [fen, orientation, lastMove, movable, editable]);

  // Arrows are chessground's "auto shapes", drawn over the board and replaced as a whole.
  useEffect(() => {
    boardRef.current?.setAutoShapes(
      (arrows ?? []).map(({ from, to, best }) => ({
        orig: from,
        dest: to,
        brush: best ? "green" : "paleGrey",
      })),
    );
  }, [arrows]);

  return (
    <div
      ref={containerRef}
      className={styles.board}
      role="img"
      aria-label={label ?? t("board.label")}
    />
  );
}
