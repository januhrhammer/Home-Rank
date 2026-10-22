import "@lichess-org/chessground/assets/chessground.base.css";
import "@lichess-org/chessground/assets/chessground.brown.css";
import "@lichess-org/chessground/assets/chessground.cburnett.css";

import { Chessground } from "@lichess-org/chessground";
import type { Api } from "@lichess-org/chessground/api";
import type { Color } from "@lichess-org/chessground/types";
import { useEffect, useRef } from "react";

import { t } from "../../lib/i18n";
import styles from "./Board.module.css";

export interface BoardProps {
  /** The position in FEN notation. */
  fen: string;
  /** Which side is shown at the bottom. */
  orientation?: Color;
}

/**
 * A chessboard showing one position, view-only for now.
 *
 * The only place in the app that uses chessground. chessground changes the page directly
 * instead of going through React, so the board is created once and then updated via its API.
 */
export function Board({ fen, orientation = "white" }: BoardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<Api | null>(null);
  // The props of the first render; useRef keeps its initial value for good.
  const initialRef = useRef({ fen, orientation });

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

  // Follow later changes of position or orientation; chessground animates the moves.
  useEffect(() => {
    boardRef.current?.set({ fen, orientation });
  }, [fen, orientation]);

  return (
    <div ref={containerRef} className={styles.board} role="img" aria-label={t("board.label")} />
  );
}
