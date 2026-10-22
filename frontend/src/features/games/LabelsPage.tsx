import { useQuery } from "@tanstack/react-query";
import { Button } from "react-aria-components";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import { type Collection, collectionsQuery, type Tag, tagsQuery } from "./games";
import { DeleteDialog, EditDialog } from "./LabelDialogs";
import type { LabelKind } from "./labels";
import styles from "./LabelsPage.module.css";

/** All of the user's collections and tags, to rename, delete, open or export them. */
export function LabelsPage() {
  const collections = useQuery(collectionsQuery);
  const tags = useQuery(tagsQuery);
  return (
    <div className={styles.page}>
      <h1>{t("labels.title")}</h1>
      <LabelSection kind="collections" items={collections.data} isError={collections.isError} />
      <LabelSection kind="tags" items={tags.data} isError={tags.isError} />
    </div>
  );
}

interface LabelSectionProps {
  kind: LabelKind;
  items: (Collection | Tag)[] | undefined;
  isError: boolean;
}

function LabelSection({ kind, items, isError }: LabelSectionProps) {
  const filter = kind === "tags" ? "tag" : "collection";
  return (
    <section className={styles.section} aria-labelledby={`${kind}-heading`}>
      <div className={styles.sectionHeader}>
        <h2 id={`${kind}-heading`}>{t(`labels.${kind}`)}</h2>
        <EditDialog
          kind={kind}
          trigger={<Button className={styles.button}>{t(`labels.new.${kind}`)}</Button>}
        />
      </div>
      {isError && (
        <p className={styles.error} role="alert">
          {t("labels.loadFailed")}
        </p>
      )}
      {items?.length === 0 && <p className={styles.none}>{t(`labels.empty.${kind}`)}</p>}
      <ul className={styles.list}>
        {items?.map((item) => (
          <li key={item.id} className={styles.item}>
            <div className={styles.info}>
              <Link className={styles.name} to={`/games?${filter}=${String(item.id)}`}>
                {item.name}
              </Link>
              <span className={styles.count}>{t("labels.count", { count: item.game_count })}</span>
              {"description" in item && item.description && (
                <p className={styles.description}>{item.description}</p>
              )}
            </div>
            <div className={styles.actions}>
              <EditDialog
                kind={kind}
                label={item}
                trigger={
                  <Button
                    className={styles.button}
                    aria-label={t("labels.edit", { name: item.name })}
                  >
                    {t("labels.editShort")}
                  </Button>
                }
              />
              <a
                className={styles.button}
                href={`/api/v1/games/export?${filter}=${String(item.id)}`}
                download
              >
                {t("labels.export")}
              </a>
              <DeleteDialog
                kind={kind}
                label={item}
                trigger={
                  <Button
                    className={styles.button}
                    aria-label={t("labels.deleteTitle", { name: item.name })}
                  >
                    {t("labels.delete")}
                  </Button>
                }
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
