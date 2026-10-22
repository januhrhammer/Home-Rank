import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  ComboBox,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Tag,
  TagGroup,
  TagList,
} from "react-aria-components";

import { t } from "../../lib/i18n";
import { collectionsQuery, type NamedRef, tagsQuery } from "./games";
import styles from "./LabelPicker.module.css";
import { type LabelKind, useLabelChange } from "./labels";

/** The suggestion that creates a new tag or collection with the typed name. */
const CREATE = "create";

interface LabelPickerProps {
  kind: LabelKind;
  gameId: number;
  /** The game's tags or collections. */
  labels: NamedRef[];
}

/**
 * A game's tags or collections as removable chips, and a field to add more: it suggests the
 * user's existing ones and offers to create a new one with the typed name.
 */
export function LabelPicker({ kind, gameId, labels }: LabelPickerProps) {
  const all = useQuery(kind === "tags" ? tagsQuery : collectionsQuery).data ?? [];
  const change = useLabelChange(kind, gameId);
  const [typed, setTyped] = useState("");

  const name = typed.trim();
  const exists = all.some((label) => label.name.toLowerCase() === name.toLowerCase());
  const suggestions = [
    ...all
      .filter((label) => !labels.some((own) => own.id === label.id))
      .map((label) => ({ id: String(label.id), name: label.name })),
    ...(name && !exists ? [{ id: CREATE, name: t("labels.create", { name }) }] : []),
  ];

  return (
    <div className={styles.picker}>
      <TagGroup
        className={styles.group}
        onRemove={(keys) => {
          for (const key of keys) {
            change.mutate({ action: "remove", labelId: Number(key) });
          }
        }}
      >
        <Label className={styles.label}>{t(`labels.${kind}`)}</Label>
        <TagList
          className={styles.tags}
          items={labels}
          renderEmptyState={() => <span className={styles.none}>{t("labels.none")}</span>}
        >
          {(label) => (
            <Tag className={styles.tag} id={label.id} textValue={label.name}>
              {label.name}
              <Button
                slot="remove"
                className={styles.remove}
                // React Aria adds the tag's name: "Remove Blunder".
                aria-label={t("labels.remove")}
              >
                ×
              </Button>
            </Tag>
          )}
        </TagList>
      </TagGroup>
      <ComboBox
        className={styles.add}
        items={suggestions}
        inputValue={typed}
        onInputChange={setTyped}
        // Nothing stays selected: choosing a suggestion adds it and empties the field.
        value={null}
        onChange={(key) => {
          if (key === null) {
            return;
          }
          change.mutate(
            key === CREATE ? { action: "create", name } : { action: "add", labelId: Number(key) },
          );
          setTyped("");
        }}
        menuTrigger="focus"
      >
        <Label className={styles.addLabel}>{t(`labels.add.${kind}`)}</Label>
        <Input className={styles.input} placeholder={t(`labels.placeholder.${kind}`)} />
        <Popover className={styles.popover}>
          <ListBox className={styles.listBox}>
            {(item: { id: string; name: string }) => (
              <ListBoxItem className={styles.option} id={item.id}>
                {item.name}
              </ListBoxItem>
            )}
          </ListBox>
        </Popover>
      </ComboBox>
      {change.isError && (
        <p className={styles.error} role="alert">
          {t("labels.failed")}
        </p>
      )}
    </div>
  );
}
