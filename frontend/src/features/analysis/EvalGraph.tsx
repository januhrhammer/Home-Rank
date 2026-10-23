import type { MouseEvent } from "react";

import { t } from "../../lib/i18n";
import type { PositionEval } from "./analysis";
import styles from "./EvalGraph.module.css";

interface EvalGraphProps {
  /** The main line's evaluations, the starting position first. */
  positions: PositionEval[];
  /** The shown position's index in the main line; null in a variation. */
  current: number | null;
  /** Called with the index of the position clicked. */
  onSelect: (index: number) => void;
}

const HEIGHT = 100;

/**
 * White's winning chances over the game: above the middle line White is better, below Black.
 * Weak moves are marked in their colour. Click to go to a position; the keyboard steps
 * through the moves instead.
 */
export function EvalGraph({ positions, current, onSelect }: EvalGraphProps) {
  const last = positions.length - 1;
  if (last < 1) {
    return null;
  }
  const y = (win: number) => HEIGHT - win;
  const points = positions.map((p, i) => `${String(i)},${String(y(p.win_percent))}`).join(" ");
  const area = `0,${String(HEIGHT)} ${points} ${String(last)},${String(HEIGHT)}`;

  const select = (event: MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const index = Math.round(((event.clientX - box.left) / box.width) * last);
    onSelect(Math.max(0, Math.min(last, index)));
  };

  return (
    <svg
      className={styles.graph}
      viewBox={`0 0 ${String(last)} ${String(HEIGHT)}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={t("analysis.graph")}
      onClick={select}
    >
      <polygon className={styles.area} points={area} />
      <line className={styles.middle} x1={0} x2={last} y1={HEIGHT / 2} y2={HEIGHT / 2} />
      <polyline className={styles.curve} points={points} />
      {current !== null && current <= last && (
        <line className={styles.current} x1={current} x2={current} y1={0} y2={HEIGHT} />
      )}
      {positions.map((p, i) =>
        p.move_class && p.move_class !== "good" ? (
          <line
            key={p.ply}
            className={styles[p.move_class]}
            data-class={p.move_class}
            x1={i}
            x2={i}
            y1={y(p.win_percent)}
            y2={y(p.win_percent)}
          />
        ) : null,
      )}
    </svg>
  );
}
