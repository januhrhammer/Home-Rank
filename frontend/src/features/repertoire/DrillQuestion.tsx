import { useRef, useState } from "react";
import { VisuallyHidden } from "react-aria-components";

import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import { withFigurines } from "../games";
import { boardMove, legalDests, squaresOf, turnOf } from "../training";
import { type Answer, type DrillStep, fenAfter, judge } from "./drill";
import styles from "./DrillPage.module.css";
import { MoveForm } from "./MoveForm";

interface DrillQuestionProps {
  step: DrillStep;
  /** The move that led to the position, as UCI ("" at the start), to highlight. */
  lastMoveUci: string;
  orientation: "white" | "black";
  figurines: boolean;
  /** Called once, when the move was found (correct) or shown after a wrong one. */
  onAnswered: (correct: boolean, elapsedMs: number) => void;
}

/**
 * Asks for one of the user's moves on the board. Another of the repertoire's own moves in the
 * position isn't wrong: the user is asked for the other one. A wrong move ends the question,
 * and the move asked for is shown on the board (ADR 0016).
 */
export function DrillQuestion({
  step,
  lastMoveUci,
  orientation,
  figurines,
  onAnswered,
}: DrillQuestionProps) {
  const [startedAt] = useState(() => Date.now());
  const [answer, setAnswer] = useState<Answer | null>(null);
  const done = answer === "right" || answer === "wrong";

  // Set at once, not on the next render: a second move arriving before that is ignored.
  const answeredRef = useRef(false);

  const play = (uci: string) => {
    if (answeredRef.current) {
      return;
    }
    const result = judge(step, uci);
    answeredRef.current = result !== "other";
    setAnswer(result);
    if (result !== "other") {
      onAnswered(result === "right", Date.now() - startedAt);
    }
  };

  return (
    <div className={styles.question}>
      <Board
        // The board shows the position asked about until the move is found or shown.
        fen={done ? fenAfter(step.fen, step.move_uci) : step.fen}
        orientation={orientation}
        lastMove={squaresOf(done ? step.move_uci : lastMoveUci)}
        label={t("drill.board")}
        movable={
          done
            ? undefined
            : {
                color: turnOf(step.fen),
                dests: legalDests(step.fen),
                onMove: (from, to) => {
                  play(boardMove(step.fen, from, to, step.move_uci));
                },
              }
        }
      />
      {/* Announced by screen readers without interrupting. */}
      <p role="status" className={styles.status} data-answer={answer ?? undefined}>
        {answer === null && t(`drill.yourMove.${turnOf(step.fen)}`)}
        {answer === "other" && t("drill.other")}
        {answer === "right" && t("drill.right")}
        {answer === "wrong" && t("drill.wrong")}
        {done && (
          <>
            {" "}
            <MoveText san={step.move_san} figurines={figurines} />
          </>
        )}
      </p>
      {!done && <MoveForm label={t("drill.typeMove")} fen={step.fen} onMove={play} />}
      {done && step.comment && <p className={styles.comment}>{step.comment}</p>}
    </div>
  );
}

/** A move shown with figurines if asked for, and read out in letters by screen readers. */
export function MoveText({ san, figurines }: { san: string; figurines: boolean }) {
  const shown = figurines ? withFigurines(san) : san;
  if (shown === san) {
    return <span className={styles.move}>{san}</span>;
  }
  return (
    <span className={styles.move}>
      <span aria-hidden="true">{shown}</span>
      <VisuallyHidden elementType="span">{san}</VisuallyHidden>
    </span>
  );
}
