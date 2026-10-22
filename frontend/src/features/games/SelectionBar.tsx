import { useState } from "react";
import { Button } from "react-aria-components";

import { t } from "../../lib/i18n";
import { LabelAdder } from "./LabelPicker";
import { type LabelKind, useLabelChange } from "./labels";
import styles from "./SelectionBar.module.css";

interface SelectionBarProps {
  selected: Set<number>;
  /** The list's sort, so the exported file has the games in the order shown. */
  sort: string;
  onClear: () => void;
}

/** What can be done with the selected games: tag them, collect them, export them. */
export function SelectionBar({ selected, sort, onClear }: SelectionBarProps) {
  const ids = [...selected];
  const exportQuery = new URLSearchParams([
    ...ids.map((id) => ["ids", String(id)]),
    ["sort", sort],
  ]);
  return (
    <div className={styles.bar} role="toolbar" aria-label={t("selection.label")}>
      <span className={styles.count}>{t("selection.count", { count: ids.length })}</span>
      <BulkAdder kind="tags" gameIds={ids} />
      <BulkAdder kind="collections" gameIds={ids} />
      <a className={styles.button} href={`/api/v1/games/export?${exportQuery.toString()}`} download>
        {t("labels.export")}
      </a>
      <Button className={styles.button} onPress={onClear}>
        {t("selection.clear")}
      </Button>
    </div>
  );
}

/** Adds a tag or collection to all selected games, and says so once done. */
function BulkAdder({ kind, gameIds }: { kind: LabelKind; gameIds: number[] }) {
  const change = useLabelChange(kind, gameIds);
  const [done, setDone] = useState<string | null>(null);
  return (
    <div className={styles.adder}>
      <LabelAdder
        kind={kind}
        onChoose={(choice) => {
          setDone(null);
          change.mutate(choice, {
            onSuccess: () => {
              setDone(t(`selection.done.${kind}`, { count: gameIds.length }));
            },
          });
        }}
      />
      {/* Announced by screen readers without moving the focus. */}
      <span role="status" className={change.isError ? styles.error : styles.done}>
        {change.isError ? t("labels.failed") : done}
      </span>
    </div>
  );
}
