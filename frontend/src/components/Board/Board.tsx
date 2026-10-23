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
}

/**
 * A chessboard showing one position, on which the user can also move when `movable` says so.
 *
 * The only place in the app that uses chessground. chessground changes the page directly
 * instead of going through React, so the board is created once and then updated via its API.
 */
export function Board({ fen, orientation = "white", lastMove, label, movable }: BoardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<Api | null>(null);
  // The props of the first render; useRef keeps its initial value for good.
  const initialRef = useRef({ fen, orientation, lastMove });
  // The latest move handler, for chessground's event, which is set up only once.
  const onMoveRef = useRef<Movable["onMove"] | undefined>(undefined);
  useEffect(() => {
    onMoveRef.current = movable?.onMove;
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
      movable: {
        free: false,
        showDests: true,
        events: {
          after: (from, to) => {
            onMoveRef.current?.(from, to);
          },
        },
      },
    });
    return () => {
      boardRef.current?.destroy();
      boardRef.current = null;
    };
  }, []);

  // Follow later changes; chessground animates the moves. Without `movable` the board takes no
  // moves at all; with it, only the given colour's, to the given squares.
  useEffect(() => {
    boardRef.current?.set({
      fen,
      orientation,
      lastMove,
      turnColor: movable?.color ?? orientation,
      movable: { color: movable?.color, dests: movable?.dests ?? new Map() },
      draggable: { enabled: movable !== undefined },
      selectable: { enabled: movable !== undefined },
    });
  }, [fen, orientation, lastMove, movable]);

  return (
    <div
      ref={containerRef}
      className={styles.board}
      role="img"
      aria-label={label ?? t("board.label")}
    />
  );
}
