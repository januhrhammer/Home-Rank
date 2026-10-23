import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { useNotation } from "../games";
import { Ratings, type Review, squaresOf, useChangeRating } from "../training";
import { type DrillStep, fenAfter, lineQuery, nextDueQuery, useDrillReview } from "./drill";
import styles from "./DrillPage.module.css";
import { DrillQuestion, MoveText } from "./DrillQuestion";
import { type Repertoire, REPERTOIRE_KEY, repertoireQuery } from "./repertoire";
import { START_FEN } from "./tree";

/** How long the opponent "thinks" before their move is played, in milliseconds. */
const OPPONENT_DELAY = 500;
/** How long an answer stays on the board before a line goes on, in milliseconds. */
const ANSWER_DELAY = 900;

/**
 * Drilling a repertoire: the cards due one by one ("due"), or whole lines from the start
 * ("line"), with the opponent's moves played automatically. The mode is in the address
 * (?mode=line, and ?through=<move id> for a line through that move).
 */
export function DrillPage() {
  const repertoireId = Number(useParams().repertoireId);
  const repertoire = useQuery(repertoireQuery(repertoireId));
  const { params } = useUrlParams();
  const mode = params.get("mode") === "line" ? "line" : "due";

  if (repertoire.isError) {
    const notFound = repertoire.error instanceof ApiError && repertoire.error.status === 404;
    return <p role="alert">{t(notFound ? "repertoire.notFound" : "repertoire.loadFailed")}</p>;
  }
  if (!repertoire.data) {
    return null;
  }
  const base = `/repertoires/${String(repertoireId)}`;
  return (
    <>
      <header className={styles.header}>
        <p className={styles.back}>
          <Link to={base}>{t("drill.backTo", { name: repertoire.data.name })}</Link>
        </p>
        <h1 className={styles.title}>{t("drill.title", { name: repertoire.data.name })}</h1>
        <nav className={styles.modes} aria-label={t("drill.modes")}>
          <Link
            className={styles.mode}
            to={`${base}/drill`}
            aria-current={mode === "due" ? "page" : undefined}
          >
            {t("drill.due")}
          </Link>
          <Link
            className={styles.mode}
            to={`${base}/drill?mode=line`}
            aria-current={mode === "line" ? "page" : undefined}
          >
            {t("drill.lines")}
          </Link>
        </nav>
      </header>
      {mode === "due" ? (
        <DueDrill repertoire={repertoire.data} />
      ) : (
        <LineDrill repertoire={repertoire.data} through={Number(params.get("through")) || null} />
      )}
    </>
  );
}

/** The repertoire's cards that are due, the one due longest first. */
function DueDrill({ repertoire }: { repertoire: Repertoire }) {
  const next = useQuery(nextDueQuery(repertoire.id));
  const review = useDrillReview();
  const changeRating = useChangeRating();
  const queryClient = useQueryClient();
  const [notation] = useNotation();
  const [result, setResult] = useState<Review | null>(null);
  // Counts the cards shown, so the same card coming back starts afresh.
  const [round, setRound] = useState(0);

  if (next.isError) {
    return <p role="alert">{t("drill.loadFailed")}</p>;
  }
  if (!next.data) {
    return null;
  }
  const { step, last_move_uci: lastMoveUci, due } = next.data;
  if (step === null || step.card_id === null) {
    return (
      <p className={styles.empty}>
        {t("drill.nothingDue")}{" "}
        <Link to={`/repertoires/${String(repertoire.id)}/drill?mode=line`}>
          {t("drill.tryLines")}
        </Link>
      </p>
    );
  }
  const cardId = step.card_id;
  const goOn = () => {
    setResult(null);
    setRound((n) => n + 1);
    void queryClient.invalidateQueries({ queryKey: REPERTOIRE_KEY });
  };

  return (
    <div className={styles.drill}>
      <div className={styles.boardColumn}>
        <DrillQuestion
          key={`${String(cardId)}-${String(round)}`}
          step={step}
          lastMoveUci={lastMoveUci}
          orientation={repertoire.color}
          figurines={notation === "figurines"}
          onAnswered={(correct, elapsedMs) => {
            review.mutate({ cardId, correct, elapsedMs }, { onSuccess: setResult });
          }}
        />
      </div>
      <div className={styles.panel}>
        <p className={styles.muted}>{t("drill.dueCount", { count: due })}</p>
        {result && (
          <>
            <Ratings
              current={result.rating}
              onChange={(rating) => {
                changeRating.mutate({ reviewId: result.id, rating }, { onSuccess: setResult });
              }}
            />
            <Button className={styles.primary} onPress={goOn}>
              {t("drill.next")}
            </Button>
          </>
        )}
        {(review.isError || changeRating.isError) && (
          <p className={styles.error} role="alert">
            {t("drill.reviewFailed")}
          </p>
        )}
      </div>
    </div>
  );
}

/** One line after another, from the start to the end of the repertoire. */
function LineDrill({ repertoire, through }: { repertoire: Repertoire; through: number | null }) {
  const lineOptions = lineQuery(repertoire.id, through);
  const line = useQuery(lineOptions);
  const { setParam } = useUrlParams();
  const queryClient = useQueryClient();
  const [round, setRound] = useState(0);

  if (line.isError) {
    return <p role="alert">{t("drill.loadFailed")}</p>;
  }
  if (!line.data) {
    return null;
  }
  if (line.data.length === 0) {
    return <p className={styles.empty}>{t("drill.noLine")}</p>;
  }
  return (
    <LinePlayer
      key={`${String(round)}-${String(line.dataUpdatedAt)}`}
      repertoire={repertoire}
      steps={line.data}
      onAgain={() => {
        setRound((n) => n + 1);
      }}
      onNextLine={() => {
        void queryClient.invalidateQueries({ queryKey: REPERTOIRE_KEY, type: "inactive" });
        if (through === null) {
          void queryClient.refetchQueries({ queryKey: lineOptions.queryKey });
        } else {
          // Forget any earlier line without a chosen move, so a new one is fetched.
          queryClient.removeQueries({ queryKey: lineQuery(repertoire.id, null).queryKey });
          setParam("through", null);
        }
      }}
    />
  );
}

interface LinePlayerProps {
  repertoire: Repertoire;
  steps: DrillStep[];
  onAgain: () => void;
  onNextLine: () => void;
}

function LinePlayer({ repertoire, steps, onAgain, onNextLine }: LinePlayerProps) {
  const review = useDrillReview();
  const [notation] = useNotation();
  // The step being played; steps.length once the line is done.
  const [index, setIndex] = useState(0);
  // Whether each of the user's moves was found, in order.
  const [answers, setAnswers] = useState<boolean[]>([]);
  const step = steps[index];
  const lastMoveUci = steps[index - 1]?.move_uci ?? "";
  const figurines = notation === "figurines";

  // The opponent's moves are played for them, after a moment.
  useEffect(() => {
    if (step === undefined || step.card_id !== null) {
      return;
    }
    const timer = window.setTimeout(() => {
      setIndex((i) => i + 1);
    }, OPPONENT_DELAY);
    return () => {
      window.clearTimeout(timer);
    };
  }, [step]);

  // After an answer, the board shows it for a moment before the line goes on.
  const [answeredAt, setAnsweredAt] = useState<number | null>(null);
  useEffect(() => {
    if (answeredAt === null) {
      return;
    }
    const timer = window.setTimeout(() => {
      setAnsweredAt(null);
      setIndex((i) => i + 1);
    }, ANSWER_DELAY);
    return () => {
      window.clearTimeout(timer);
    };
  }, [answeredAt]);

  const last = steps.at(-1);
  const finalFen = last ? fenAfter(last.fen, last.move_uci) : START_FEN;
  const right = answers.filter(Boolean).length;

  // The card of the move asked for now; null while the opponent moves or the line is done.
  const cardId = step?.card_id ?? null;

  return (
    <div className={styles.drill}>
      <div className={styles.boardColumn}>
        {step !== undefined && cardId !== null ? (
          <DrillQuestion
            key={index}
            step={step}
            lastMoveUci={lastMoveUci}
            orientation={repertoire.color}
            figurines={figurines}
            onAnswered={(correct, elapsedMs) => {
              setAnswers((list) => [...list, correct]);
              setAnsweredAt(Date.now());
              review.mutate({ cardId, correct, elapsedMs });
            }}
          />
        ) : (
          <>
            <Board
              fen={step ? step.fen : finalFen}
              orientation={repertoire.color}
              lastMove={squaresOf(step ? lastMoveUci : (last?.move_uci ?? ""))}
              label={t("drill.board")}
            />
            <p role="status" className={styles.status}>
              {step ? t("drill.opponent") : t("drill.lineDone", { right, asked: answers.length })}
            </p>
          </>
        )}
      </div>
      <div className={styles.panel}>
        <h2 className={styles.heading}>{t("drill.line")}</h2>
        <p className={styles.line}>
          {steps.slice(0, index).map((played, i) => (
            <span
              key={played.move_id}
              data-wrong={answers[userIndex(steps, i)] === false || undefined}
            >
              {i % 2 === 0 && <span className={styles.number}>{`${String(i / 2 + 1)}.`}</span>}
              <MoveText san={played.move_san} figurines={figurines} />{" "}
            </span>
          ))}
        </p>
        {!step && (
          <div className={styles.buttons}>
            <Button className={styles.primary} onPress={onNextLine}>
              {t("drill.nextLine")}
            </Button>
            <Button className={styles.secondary} onPress={onAgain}>
              {t("drill.again")}
            </Button>
          </div>
        )}
        {review.isError && (
          <p className={styles.error} role="alert">
            {t("drill.reviewFailed")}
          </p>
        )}
      </div>
    </div>
  );
}

/** Which of the user's answers belongs to the step at `i`; -1 for the opponent's moves. */
function userIndex(steps: DrillStep[], i: number): number {
  if (steps[i]?.card_id === null) {
    return -1;
  }
  return steps.slice(0, i).filter((s) => s.card_id !== null).length;
}
