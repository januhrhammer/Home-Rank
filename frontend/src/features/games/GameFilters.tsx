import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { Input, Label, SearchField } from "react-aria-components";

import { type Option, Select } from "../../components/Select";
import { type MessageKey, t } from "../../lib/i18n";
import styles from "./GameFilters.module.css";
import { collectionsQuery, tagsQuery } from "./games";

/** How long text filters wait after the last keystroke before they apply, in milliseconds. */
export const TYPING_PAUSE = 400;

interface GameFiltersProps {
  params: URLSearchParams;
  /** Set a filter in the address; null removes it. */
  setFilter: (name: string, value: string | null) => void;
}

const COLORS: Option[] = [
  { id: "white", name: t("games.color.white") },
  { id: "black", name: t("games.color.black") },
];
const OUTCOMES: Option[] = [
  { id: "win", name: t("games.outcome.win") },
  { id: "draw", name: t("games.outcome.draw") },
  { id: "loss", name: t("games.outcome.loss") },
];
const TIME_CLASSES: Option[] = [
  { id: "bullet", name: t("games.timeClass.bullet") },
  { id: "blitz", name: t("games.timeClass.blitz") },
  { id: "rapid", name: t("games.timeClass.rapid") },
  { id: "classical", name: t("games.timeClass.classical") },
  { id: "correspondence", name: t("games.timeClass.correspondence") },
];

export function GameFilters({ params, setFilter }: GameFiltersProps) {
  const tags = useQuery(tagsQuery);
  const collections = useQuery(collectionsQuery);
  const named = (items: { id: number; name: string }[] = []): Option[] =>
    items.map((item) => ({ id: String(item.id), name: item.name }));

  const select = (name: string, label: MessageKey, choices: Option[]) => (
    <Select
      label={t(label)}
      anyOption={t("games.filter.any")}
      options={choices}
      value={params.get(name)}
      onChange={(value) => {
        setFilter(name, value);
      }}
    />
  );

  return (
    <div className={styles.filters} role="search" aria-label={t("games.filter.label")}>
      {/* Five to a row on a wide screen: who played and how it ended, the opening; then how
          fast, when, and the user's own tags and collections. */}
      <TextFilter name="player" label="games.filter.player" params={params} setFilter={setFilter} />
      {select("color", "games.filter.color", COLORS)}
      {select("outcome", "games.filter.outcome", OUTCOMES)}
      <TextFilter
        name="opening"
        label="games.filter.opening"
        params={params}
        setFilter={setFilter}
      />
      <TextFilter name="eco" label="games.filter.eco" params={params} setFilter={setFilter} />
      {select("time_class", "games.filter.timeClass", TIME_CLASSES)}
      <DateFilter
        name="date_from"
        label="games.filter.from"
        params={params}
        setFilter={setFilter}
      />
      <DateFilter name="date_to" label="games.filter.to" params={params} setFilter={setFilter} />
      {select("tag", "games.filter.tag", named(tags.data))}
      {select("collection", "games.filter.collection", named(collections.data))}
    </div>
  );
}

interface FieldProps extends GameFiltersProps {
  name: string;
  label: MessageKey;
}

/** A search field that applies once the typing pauses, not on every keystroke. */
function TextFilter({ name, label, params, setFilter }: FieldProps) {
  const applied = params.get(name) ?? "";
  const [typed, setTyped] = useState(applied);

  useEffect(() => {
    if (typed === applied) {
      return undefined;
    }
    const timer = setTimeout(() => {
      setFilter(name, typed.trim() || null);
    }, TYPING_PAUSE);
    return () => {
      clearTimeout(timer);
    };
  }, [typed, applied, name, setFilter]);

  return (
    <SearchField className={styles.field} value={typed} onChange={setTyped}>
      <Label className={styles.label}>{t(label)}</Label>
      <Input className={styles.input} />
    </SearchField>
  );
}

/** The browser's own date picker; it applies as soon as a date is complete. */
function DateFilter({ name, label, params, setFilter }: FieldProps) {
  const inputId = useId();
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {t(label)}
      </label>
      <input
        id={inputId}
        className={styles.input}
        type="date"
        value={params.get(name) ?? ""}
        onChange={(event) => {
          setFilter(name, event.target.value || null);
        }}
      />
    </div>
  );
}
