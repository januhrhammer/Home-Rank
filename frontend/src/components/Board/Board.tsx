import "@lichess-org/chessground/assets/chessground.base.css";
import "@lichess-org/chessground/assets/chessground.brown.css";
import "@lichess-org/chessground/assets/chessground.cburnett.css";

import { Chessground } from "@lichess-org/chessground";
import type { Api } from "@lichess-org/chessground/api";
import type { Color, Key } from "@lichess-org/chessground/types";
import { useEffect, useRef } from "react";

import { t } from "../../lib/i18n";
import styles from "./Board.module.css";

export interface BoardProps {
  /** The position in FEN notation. */
  fen: string;
  /** Which side is shown at the bottom. */
  orientation?: Color;
  /** The squares the last move went from and to, highlighted on the board. */
  lastMove?: Key[];
  /** What the board shows, for screen readers, e.g. "Position after 12. Nf3". */
  label?: string;
}

/**
 * A chessboard showing one position, view-only for now.
 *
 * The only place in the app that uses chessground. chessground changes the page directly
 * instead of going through React, so the board is created once and then updated via its API.
 */
export function Board({ fen, orientation = "white", lastMove, label }: BoardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<Api | null>(null);
  // The props of the first render; useRef keeps its initial value for good.
  const initialRef = useRef({ fen, orientation, lastMove });

  // Create the board once, already showing the first position: created empty, chessground
  // would show the starting position and then animate to ours. Remove the board, with its
  // event listeners, when the component goes away.
  useEffect(() => {
    if (containerRef.current === null) {
      return;
    }
    boardRef.current = Chessground(containerRef.current, { ...initialRef.current, viewOnly: true });
    return () => {
      boardRef.current?.destroy();
      boardRef.current = null;
    };
  }, []);

  // Follow later changes; chessground animates the moves.
  useEffect(() => {
    boardRef.current?.set({ fen, orientation, lastMove });
  }, [fen, orientation, lastMove]);

  return (
    <div
      ref={containerRef}
      className={styles.board}
      role="img"
      aria-label={label ?? t("board.label")}
    />
  );
}
