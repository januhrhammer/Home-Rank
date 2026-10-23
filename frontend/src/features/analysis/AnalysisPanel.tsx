import { Chess } from "chessops/chess";
import { parseFen } from "chessops/fen";
import { makeSanVariation } from "chessops/san";
import { parseUci } from "chessops/util";
import { Button, ProgressBar } from "react-aria-components";

import { t } from "../../lib/i18n";
import {
  formatScore,
  type GameAnalysis,
  isActive,
  type PositionEval,
  useAnalyse,
} from "./analysis";
import styles from "./AnalysisPanel.module.css";

/** How much deeper "Analyse deeper" searches than the analysis there is. */
const DEEPER = 4;
const MAX_DEPTH = 30;

interface AnalysisPanelProps {
  gameId: number;
  analysis: GameAnalysis | undefined;
  /** The shown position's evaluation, and the position itself as FEN. */
  position: PositionEval | undefined;
  fen: string;
  /** Formats a line of moves in the user's notation (figurines or letters). */
  formatMoves: (san: string) => string;
}

/** Stockfish's view of the game: start an analysis, follow it, and read what it found. */
export function AnalysisPanel({
  gameId,
  analysis,
  position,
  fen,
  formatMoves,
}: AnalysisPanelProps) {
  const analyse = useAnalyse(gameId);
  const run = analysis?.run ?? null;
  const summary = analysis?.summary ?? null;

  return (
    <section className={styles.panel} aria-labelledby="analysis-heading">
      <h2 id="analysis-heading" className={styles.heading}>
        {t("analysis.title")}
      </h2>
      {isActive(run) && run !== null ? (
        <Progress
          done={run.positions_done}
          total={run.positions_total}
          queued={run.status === "queued"}
        />
      ) : summary === null ? (
        <>
          {run?.status === "failed" && (
            <p className={styles.error}>{t("analysis.failed", { reason: run.error })}</p>
          )}
          <Button
            className={styles.button}
            isPending={analyse.isPending}
            onPress={() => {
              analyse.mutate(undefined);
            }}
          >
            {t("analysis.start")}
          </Button>
        </>
      ) : (
        <>
          {analysis && <Summary analysis={analysis} />}
          {summary.depth + DEEPER <= MAX_DEPTH && (
            <Button
              className={styles.secondary}
              isPending={analyse.isPending}
              onPress={() => {
                analyse.mutate(summary.depth + DEEPER);
              }}
            >
              {t("analysis.deeper", { depth: summary.depth + DEEPER })}
            </Button>
          )}
        </>
      )}
      {analyse.isError && (
        <p className={styles.error} role="alert">
          {t("analysis.startFailed")}
        </p>
      )}
      {position && <BestLine position={position} fen={fen} formatMoves={formatMoves} />}
    </section>
  );
}

function Progress({ done, total, queued }: { done: number; total: number; queued: boolean }) {
  return (
    <ProgressBar
      className={styles.progress}
      value={total > 0 ? (done / total) * 100 : 0}
      isIndeterminate={queued}
      aria-label={t("analysis.progress")}
    >
      {({ percentage, isIndeterminate }) => (
        <>
          <span className={styles.progressText}>
            {queued ? t("analysis.queued") : t("analysis.running", { done, total })}
          </span>
          <div className={styles.track}>
            <div
              className={styles.fill}
              data-waiting={isIndeterminate || undefined}
              style={isIndeterminate ? undefined : { width: `${String(percentage ?? 0)}%` }}
            />
          </div>
        </>
      )}
    </ProgressBar>
  );
}

function Summary({ analysis }: { analysis: GameAnalysis }) {
  const summary = analysis.summary;
  if (summary === null) {
    return null;
  }
  const accuracy = (value: number | null) =>
    value === null ? "–" : `${String(Math.round(value))} %`;
  const rows = [
    { side: t("analysis.white"), accuracy: summary.accuracy_white, mistakes: analysis.white },
    { side: t("analysis.black"), accuracy: summary.accuracy_black, mistakes: analysis.black },
  ];
  return (
    <>
      <table className={styles.summary}>
        <thead>
          <tr>
            <th scope="col">
              <span className={styles.hidden}>{t("analysis.side")}</span>
            </th>
            <th scope="col">{t("analysis.accuracy")}</th>
            <th scope="col" className={styles.inaccuracy}>
              {t("analysis.inaccuracies")}
            </th>
            <th scope="col" className={styles.mistake}>
              {t("analysis.mistakes")}
            </th>
            <th scope="col" className={styles.blunder}>
              {t("analysis.blunders")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.side}>
              <th scope="row">{row.side}</th>
              <td>{accuracy(row.accuracy)}</td>
              <td>{row.mistakes.inaccuracies}</td>
              <td>{row.mistakes.mistakes}</td>
              <td>{row.mistakes.blunders}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.engine}>
        {t("analysis.engine", { engine: summary.engine, depth: summary.depth })}
      </p>
    </>
  );
}

/** The engine's score and best line in the shown position, as moves to read. */
function BestLine({
  position,
  fen,
  formatMoves,
}: {
  position: PositionEval;
  fen: string;
  formatMoves: (san: string) => string;
}) {
  const line = sanLine(fen, position.pv);
  return (
    <p className={styles.line}>
      <span className={styles.score}>{formatScore(position)}</span>
      {line && <span className={styles.moves}>{formatMoves(line)}</span>}
    </p>
  );
}

/** The engine's line (UCI moves) from the position, numbered like "12. Nf3 Nc6 13. d4". */
export function sanLine(fen: string, uci: string[]): string {
  const setup = parseFen(fen);
  if (setup.isErr) {
    return "";
  }
  const position = Chess.fromSetup(setup.value);
  if (position.isErr) {
    return "";
  }
  const moves = uci.map(parseUci).filter((move) => move !== undefined);
  return makeSanVariation(position.value, moves);
}
