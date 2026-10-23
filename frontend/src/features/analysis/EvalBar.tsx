import { t } from "../../lib/i18n";
import { formatScore, type PositionEval } from "./analysis";
import styles from "./EvalBar.module.css";

interface EvalBarProps {
  /** The shown position's evaluation; undefined while there is none (e.g. in a variation). */
  position: PositionEval | undefined;
  /** The board's orientation: White's share grows from the bottom when White is below. */
  orientation: "white" | "black";
}

/** A bar beside the board: White's winning chances in light, Black's in dark. */
export function EvalBar({ position, orientation }: EvalBarProps) {
  const white = position?.win_percent ?? 50;
  const score = position ? formatScore(position) : "";
  return (
    <div
      className={styles.bar}
      data-orientation={orientation}
      data-empty={position === undefined || undefined}
      role="meter"
      aria-label={t("analysis.bar")}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(white)}
      aria-valuetext={position ? t("analysis.barValue", { score }) : t("analysis.noEval")}
    >
      <div className={styles.white} style={{ height: `${String(white)}%` }} />
      <span className={styles.score} aria-hidden="true">
        {score}
      </span>
    </div>
  );
}
