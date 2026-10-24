import { useQuery } from "@tanstack/react-query";
import { Fragment } from "react";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import { useNotation } from "../games";
import styles from "./Conflicts.module.css";
import { MoveText } from "./DrillQuestion";
import { conflictsQuery, type RepertoireLine } from "./repertoire";

/**
 * Where the repertoire's lines play different moves of the user's (ADR 0020): each position
 * with its moves and the lines that play them, linked. Nothing when the lines agree.
 */
export function Conflicts({
  repertoireId,
  lines,
}: {
  repertoireId: number;
  lines: RepertoireLine[];
}) {
  const conflicts = useQuery(conflictsQuery(repertoireId));
  const [notation] = useNotation();
  if (!conflicts.data || conflicts.data.length === 0) {
    return null;
  }
  const byName = new Map(lines.map((line) => [line.name, line]));
  return (
    <section aria-labelledby="conflicts-heading" className={styles.panel}>
      <h2 id="conflicts-heading" className={styles.heading}>
        {t("repertoire.conflicts")}
      </h2>
      <ul className={styles.list}>
        {conflicts.data.map((conflict) => {
          const [, side, , , , fullmove] = conflict.fen.split(" ");
          const number = `${fullmove ?? ""}${side === "w" ? "." : "…"}`;
          return (
            <li key={conflict.fen}>
              {conflict.choices.map((choice, index) => (
                <Fragment key={choice.move_uci}>
                  {index > 0 && " · "}
                  {number}
                  <MoveText san={choice.move_san} figurines={notation === "figurines"} />{" "}
                  {choice.lines.map((name, n) => {
                    const line = byName.get(name);
                    return (
                      <Fragment key={name}>
                        {n > 0 && ", "}
                        {line ? <Link to={`?line=${String(line.id)}`}>{name}</Link> : name}
                      </Fragment>
                    );
                  })}
                </Fragment>
              ))}
            </li>
          );
        })}
      </ul>
      <p className={styles.hint}>{t("repertoire.conflictsHint")}</p>
    </section>
  );
}
