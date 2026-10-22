import { useState } from "react";
import { Button } from "react-aria-components";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { GameFilters } from "./GameFilters";
import styles from "./GameListPage.module.css";
import { type GameSort, listQuery, PAGE_SIZE, pageOf, useGames } from "./games";
import { GameTable } from "./GameTable";
import { SelectionBar } from "./SelectionBar";

export function GameListPage() {
  const { params, setParam } = useUrlParams();
  const query = listQuery(params);
  const games = useGames(query);
  const page = pageOf(params);

  // The selected games belong to the list they were chosen in: with other filters or another
  // page, nothing is selected, so no action ever applies to games that aren't shown.
  const listKey = JSON.stringify(query);
  const [selection, setSelection] = useState(() => ({ listKey, ids: new Set<number>() }));
  const selected = selection.listKey === listKey ? selection.ids : new Set<number>();
  const setSelected = (ids: Set<number>) => {
    setSelection({ listKey, ids });
  };

  /** Change a filter or the sort; either starts again on the first page. */
  const setFilter = (name: string, value: string | null) => {
    setParam(name, value, ["page"]);
  };

  const hasFilters = [...params.keys()].some((name) => name !== "sort" && name !== "page");

  return (
    <>
      <h1>{t("games.title")}</h1>
      <GameFilters params={params} setFilter={setFilter} />
      {games.isError && (
        <p className={styles.error} role="alert">
          {t("games.loadFailed")}
        </p>
      )}
      {games.data?.total === 0 &&
        (hasFilters ? (
          <p>
            {t("games.noMatch")} <Link to="/games">{t("games.filter.clear")}</Link>
          </p>
        ) : (
          <p>
            {t("games.none")} <Link to="/import">{t("games.importLink")}</Link>
          </p>
        ))}
      {games.data !== undefined && games.data.total > 0 && (
        <>
          <GameTable
            games={games.data.items}
            sort={query.sort ?? "-date"}
            onSortChange={(sort: GameSort) => {
              setFilter("sort", sort);
            }}
            selected={selected}
            onSelectionChange={setSelected}
          />
          {selected.size > 0 && (
            <SelectionBar
              selected={selected}
              sort={query.sort ?? "-date"}
              onClear={() => {
                setSelected(new Set());
              }}
            />
          )}
          <Pagination
            page={page}
            total={games.data.total}
            onPageChange={(next) => {
              setParam("page", next === 1 ? null : String(next));
            }}
          />
        </>
      )}
    </>
  );
}

interface PaginationProps {
  page: number;
  total: number;
  onPageChange: (page: number) => void;
}

function Pagination({ page, total, onPageChange }: PaginationProps) {
  const first = (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, total);
  return (
    <nav className={styles.pagination} aria-label={t("games.title")}>
      <Button
        className={styles.pageButton}
        isDisabled={page === 1}
        onPress={() => {
          onPageChange(page - 1);
        }}
      >
        {t("games.previous")}
      </Button>
      <span>{t("games.range", { first, last, total })}</span>
      <Button
        className={styles.pageButton}
        isDisabled={last >= total}
        onPress={() => {
          onPageChange(page + 1);
        }}
      >
        {t("games.next")}
      </Button>
    </nav>
  );
}
