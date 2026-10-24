import { SwitchButton, SwitchField } from "react-aria-components";

import { t } from "../../lib/i18n";
import { sanLine } from "../analysis";
import { useNotation, withFigurines } from "../games";
import styles from "./EnginePanel.module.css";
import { scoreText } from "./uci";
import type { LiveAnalysis } from "./useLiveAnalysis";

/** Moves of a line shown at most: enough to see the idea, short enough to read. */
const SHOWN_MOVES = 8;

/** The switch for live analysis and, while it runs, the engine's best lines. */
export function EnginePanel({ fen, analysis }: { fen: string; analysis: LiveAnalysis }) {
  const [notation] = useNotation();
  const format = (line: string) =>
    notation === "figurines" ? line.split(" ").map(withFigurines).join(" ") : line;
  const depth = analysis.lines[0]?.depth;

  return (
    <section className={styles.panel} aria-label={t("engine.title")}>
      <div className={styles.header}>
        <SwitchField isSelected={analysis.enabled} onChange={analysis.setEnabled}>
          <SwitchButton className={styles.switch}>
            <span className={styles.track}>
              <span className={styles.thumb} />
            </span>
            {t("engine.title")}
          </SwitchButton>
        </SwitchField>
        {analysis.enabled && (
          <span className={styles.depth}>
            {depth === undefined ? t("engine.starting") : t("engine.depth", { depth })}
          </span>
        )}
      </div>
      {analysis.enabled && analysis.lines.length > 0 && (
        <ol className={styles.lines}>
          {analysis.lines.map((line) => (
            <li key={line.rank} className={styles.line}>
              <span className={styles.score}>{scoreText(line.score)}</span>{" "}
              <span className={styles.moves}>
                {format(sanLine(fen, line.moves.slice(0, SHOWN_MOVES)))}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
