import { useQuery } from "@tanstack/react-query";
import { Button } from "react-aria-components";

import { Select } from "../../components/Select";
import { t } from "../../lib/i18n";
import { databasesQuery, explorerQuery, type MoveStats, type Source, whiteScore } from "./explorer";
import styles from "./ExplorerPanel.module.css";

const numbers = new Intl.NumberFormat();

interface ExplorerPanelProps {
  fen: string;
  source: Source;
  onSourceChange: (source: Source) => void;
  /** Called with a move when it is chosen; moves are shown as buttons if given. */
  onMove?: (move: MoveStats) => void;
  /** Formats a move in the user's notation (figurines or letters). */
  formatMove: (san: string) => string;
}

/** The moves played from a position, in your games or a reference database, with results. */
export function ExplorerPanel({
  fen,
  source,
  onSourceChange,
  onMove,
  formatMove,
}: ExplorerPanelProps) {
  const databases = useQuery(databasesQuery);
  const explorer = useQuery(explorerQuery(source, fen));
  const ready = (databases.data ?? []).filter((d) => d.status === "ready");
  const value = source.kind === "mine" ? "mine" : String(source.databaseId);

  return (
    <div className={styles.panel}>
      <Select
        label={t("explorer.source")}
        anyOption={t("explorer.mine")}
        options={ready.map((d) => ({ id: String(d.id), name: d.name }))}
        value={value === "mine" ? null : value}
        onChange={(id) => {
          onSourceChange(
            id === null ? { kind: "mine" } : { kind: "reference", databaseId: Number(id) },
          );
        }}
      />
      {explorer.data?.opening && (
        <p className={styles.opening}>
          <span className={styles.eco}>{explorer.data.opening.eco}</span>{" "}
          {explorer.data.opening.name}
        </p>
      )}
      {explorer.isError && <p role="alert">{t("explorer.loadFailed")}</p>}
      {explorer.data && explorer.data.moves.length === 0 && (
        <p className={styles.empty}>{t("explorer.none")}</p>
      )}
      {explorer.data && explorer.data.moves.length > 0 && (
        <table className={styles.table}>
          <caption className={styles.caption}>
            {t("explorer.games", { count: explorer.data.games })}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("explorer.move")}</th>
              <th scope="col">{t("explorer.gamesColumn")}</th>
              <th scope="col">{t("explorer.score")}</th>
              <th scope="col">{t("explorer.rating")}</th>
              <th scope="col">{t("explorer.last")}</th>
            </tr>
          </thead>
          <tbody>
            {explorer.data.moves.map((move) => (
              <MoveRow key={move.uci} move={move} onMove={onMove} formatMove={formatMove} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function MoveRow({
  move,
  onMove,
  formatMove,
}: {
  move: MoveStats;
  onMove?: (move: MoveStats) => void;
  formatMove: (san: string) => string;
}) {
  const decided = Math.max(1, move.white + move.draws + move.black);
  const percent = (n: number) => `${String((n / decided) * 100)}%`;
  return (
    <tr>
      <th scope="row" className={styles.move}>
        {onMove ? (
          <Button
            className={styles.moveButton}
            aria-label={move.san}
            onPress={() => {
              onMove(move);
            }}
          >
            {formatMove(move.san)}
          </Button>
        ) : (
          formatMove(move.san)
        )}
      </th>
      <td>{numbers.format(move.games)}</td>
      <td>
        <span
          className={styles.bar}
          role="img"
          aria-label={t("explorer.results", {
            white: move.white,
            draws: move.draws,
            black: move.black,
            score: whiteScore(move),
          })}
        >
          <span className={styles.white} style={{ width: percent(move.white) }} />
          <span className={styles.draw} style={{ width: percent(move.draws) }} />
          <span className={styles.black} style={{ width: percent(move.black) }} />
        </span>
      </td>
      <td>{move.average_rating === null ? "–" : Math.round(move.average_rating)}</td>
      <td>{move.last_played?.slice(0, 4) ?? "–"}</td>
    </tr>
  );
}
