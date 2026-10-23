import { useQuery } from "@tanstack/react-query";

import { Select } from "../../components/Select";
import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { PuzzlePlayer } from "./PuzzlePlayer";
import { nextPuzzleQuery, type PuzzleFilters, useNextPuzzle, useStats } from "./training";
import styles from "./TrainPage.module.css";

const KINDS = ["missed", "found", "opponent_blunder"] as const;
const THEMES = ["mate", "material"] as const;

/** The filters in the address, e.g. /train?kind=missed, so a choice survives a reload. */
function filtersOf(params: URLSearchParams): PuzzleFilters {
  const kind = KINDS.find((k) => k === params.get("kind"));
  const theme = THEMES.find((k) => k === params.get("theme"));
  return { kind: kind ?? null, theme: theme ?? null };
}

export function TrainPage() {
  const { params, setParam } = useUrlParams();
  const filters = filtersOf(params);
  const next = useQuery(nextPuzzleQuery(filters));
  const goOn = useNextPuzzle();

  return (
    <div className={styles.page}>
      <h1>{t("training.title")}</h1>
      <div className={styles.filters}>
        <Select
          label={t("training.filter.kind")}
          anyOption={t("training.filter.allKinds")}
          options={KINDS.map((kind) => ({ id: kind, name: t(`training.filter.${kind}`) }))}
          value={params.get("kind")}
          onChange={(value) => {
            setParam("kind", value);
          }}
        />
        <Select
          label={t("training.filter.theme")}
          anyOption={t("training.filter.anyTheme")}
          options={THEMES.map((theme) => ({ id: theme, name: t(`training.theme.${theme}`) }))}
          value={params.get("theme")}
          onChange={(value) => {
            setParam("theme", value);
          }}
        />
      </div>
      <Stats due={next.data?.due} />
      {next.isError && <p role="alert">{t("training.loadFailed")}</p>}
      {next.data?.puzzle === null && <p className={styles.empty}>{t("training.nothingDue")}</p>}
      {next.data?.puzzle && (
        <PuzzlePlayer
          // A new puzzle starts afresh, even if it happens to be the same one again.
          key={`${String(next.data.puzzle.id)}-${next.data.puzzle.due_at}`}
          puzzle={next.data.puzzle}
          onNext={() => {
            void goOn();
          }}
        />
      )}
    </div>
  );
}

function Stats({ due }: { due: number | undefined }) {
  const stats = useStats();
  if (!stats.data) {
    return null;
  }
  const week = stats.data.weeks.at(-1);
  const rate = week && week.reviews > 0 ? Math.round((week.solved / week.reviews) * 100) : null;
  return (
    <p className={styles.stats}>
      {t("training.stats", {
        due: due ?? stats.data.due_now,
        today: stats.data.reviewed_today,
        puzzles: stats.data.puzzles,
      })}
      {rate !== null && ` · ${t("training.successRate", { rate })}`}
    </p>
  );
}
