import { useEffect, useRef, useState } from "react";
import { Button, Form, type FormProps, Input, Label, TextField } from "react-aria-components";
import { Link } from "react-router";

import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import { sanLine } from "../analysis";
import {
  begin,
  boardMove,
  legalDests,
  type Progress,
  reply,
  replyDue,
  showSolution,
  tryMove,
  turnOf,
  typedMove,
} from "./puzzle";
import styles from "./PuzzlePlayer.module.css";
import { type Puzzle, type Rating, type Review, useChangeRating, useReview } from "./training";

/** How long the opponent "thinks" before replying, in milliseconds. */
const REPLY_DELAY = 400;
const RATINGS: { value: Rating; key: "again" | "hard" | "good" | "easy" }[] = [
  { value: 1, key: "again" },
  { value: 2, key: "hard" },
  { value: 3, key: "good" },
  { value: 4, key: "easy" },
];

interface PuzzlePlayerProps {
  puzzle: Puzzle;
  onNext: () => void;
}

/** One puzzle: the user moves, the opponent replies, and the result is reviewed. */
export function PuzzlePlayer({ puzzle, onNext }: PuzzlePlayerProps) {
  const [progress, setProgress] = useState(() => begin(puzzle.fen, puzzle.last_move_uci));
  const [startedAt] = useState(() => Date.now());
  const [review, setReview] = useState<Review | null>(null);
  const reviewMutation = useReview();
  const changeRating = useChangeRating();
  const timerRef = useRef<number | undefined>(undefined);
  const solver = turnOf(puzzle.fen);

  // No reply may arrive after the puzzle is gone.
  useEffect(
    () => () => {
      window.clearTimeout(timerRef.current);
    },
    [],
  );

  const finish = (done: Progress) => {
    reviewMutation.mutate(
      { cardId: puzzle.card_id, correct: !done.wrong, elapsedMs: Date.now() - startedAt },
      { onSuccess: setReview },
    );
  };

  const move = (uci: string) => {
    const next = tryMove(progress, puzzle.solution, uci);
    setProgress(next);
    if (next.status !== "playing") {
      finish(next);
    } else if (replyDue(next, puzzle.solution)) {
      timerRef.current = window.setTimeout(() => {
        setProgress(reply(next, puzzle.solution));
      }, REPLY_DELAY);
    }
  };

  const giveUp = () => {
    window.clearTimeout(timerRef.current);
    const shown = showSolution(progress, puzzle.solution);
    setProgress(shown);
    finish(shown);
  };

  const waiting = replyDue(progress, puzzle.solution);
  const canMove = progress.status === "playing" && !waiting;

  return (
    <div className={styles.player}>
      <div className={styles.boardColumn}>
        <Board
          fen={progress.fen}
          orientation={solver}
          lastMove={progress.lastMove}
          label={t("training.board")}
          movable={
            canMove
              ? {
                  color: solver,
                  dests: legalDests(progress.fen),
                  onMove: (from, to) => {
                    move(boardMove(progress.fen, from, to, puzzle.solution[progress.step] ?? ""));
                  },
                }
              : undefined
          }
        />
      </div>
      <div className={styles.panel}>
        <h2 className={styles.task}>{t(`training.find.${solver}`)}</h2>
        <p className={styles.kind}>{t(`training.kind.${puzzle.kind}`)}</p>
        {canMove && <MoveForm fen={progress.fen} onMove={move} />}
        <Status progress={progress} puzzle={puzzle} />
        {progress.status === "playing" ? (
          <Button className={styles.secondary} onPress={giveUp}>
            {t("training.showSolution")}
          </Button>
        ) : (
          <>
            {review && (
              <Ratings
                current={review.rating}
                onChange={(rating) => {
                  changeRating.mutate({ reviewId: review.id, rating }, { onSuccess: setReview });
                }}
              />
            )}
            {reviewMutation.isError && (
              <p className={styles.error} role="alert">
                {t("training.reviewFailed")}
              </p>
            )}
            <Button className={styles.button} onPress={onNext}>
              {t("training.next")}
            </Button>
          </>
        )}
        <p className={styles.source}>
          <Link to={`/games/${String(puzzle.game.id)}`}>
            {t("training.fromGame", {
              white: puzzle.game.white || "?",
              black: puzzle.game.black || "?",
              date: puzzle.game.date_pgn,
            })}
          </Link>
        </p>
      </div>
    </div>
  );
}

/** Moves typed in, for the keyboard and screen readers: "Nf3" or "g1f3". */
function MoveForm({ fen, onMove }: { fen: string; onMove: (uci: string) => void }) {
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);

  // Typed by React Aria's Form itself: React's types and React Aria's currently disagree on
  // the name of the submit event type.
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    const uci = typedMove(fen, text);
    setInvalid(uci === null);
    if (uci !== null) {
      setText("");
      onMove(uci);
    }
  };

  return (
    <Form className={styles.moveForm} onSubmit={handleSubmit}>
      <TextField
        className={styles.field}
        value={text}
        onChange={(value) => {
          setText(value);
          setInvalid(false);
        }}
      >
        <Label className={styles.label}>{t("training.yourMove")}</Label>
        <Input className={styles.input} autoComplete="off" spellCheck={false} />
      </TextField>
      <Button className={styles.secondary} type="submit">
        {t("training.play")}
      </Button>
      {invalid && <p className={styles.error}>{t("training.notLegal")}</p>}
    </Form>
  );
}

function Status({ progress, puzzle }: { progress: Progress; puzzle: Puzzle }) {
  let text = "";
  if (progress.status === "solved") {
    text = progress.wrong ? t("training.solvedAfterMistake") : t("training.solved");
  } else if (progress.status === "shown") {
    text = t("training.solution", { moves: sanLine(puzzle.fen, puzzle.solution) });
  } else if (progress.wrong) {
    text = t("training.wrong");
  }
  return (
    // Announced by screen readers without interrupting.
    <p role="status" className={styles.status} data-result={progress.status}>
      {text}
    </p>
  );
}

function Ratings({ current, onChange }: { current: Rating; onChange: (rating: Rating) => void }) {
  return (
    <div role="group" aria-labelledby="rating-label" className={styles.ratings}>
      <span id="rating-label" className={styles.label}>
        {t("training.rating")}
      </span>
      {RATINGS.map((rating) => (
        <Button
          key={rating.value}
          className={styles.rating}
          aria-pressed={rating.value === current}
          onPress={() => {
            onChange(rating.value);
          }}
        >
          {t(`training.rating.${rating.key}`)}
        </Button>
      ))}
    </div>
  );
}
