import {
  Cell,
  CheckboxButton,
  CheckboxField,
  Column,
  Row,
  type Selection,
  type SortDescriptor,
  Table,
  TableBody,
  TableHeader,
} from "react-aria-components";

import { t } from "../../lib/i18n";
import type { GameListItem, GameSort } from "./games";
import styles from "./GameTable.module.css";

const fullDates = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" });
const monthDates = new Intl.DateTimeFormat(undefined, {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

/** A PGN date with what is known of it: "5 Mar 2024", "May 1960", "1960", or nothing. */
export function formatGameDate(datePgn: string): string {
  const [year, month, day] = datePgn.split(".");
  if (year === undefined || year.startsWith("?")) {
    return "";
  }
  if (month === undefined || month.startsWith("?")) {
    return year;
  }
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day) || 1));
  return day === undefined || day.startsWith("?")
    ? monthDates.format(date)
    : fullDates.format(date);
}

/** CSS Modules class names together; a name missing from the module is left out. */
function classes(...names: (string | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}

/** The sort in the address ("-date") as React Aria's table describes it, and back. */
function descriptorOf(sort: GameSort): SortDescriptor {
  return {
    column: sort.replace(/^-/, ""),
    direction: sort.startsWith("-") ? "descending" : "ascending",
  };
}

function sortOf(descriptor: SortDescriptor): GameSort {
  // The sortable columns' ids are sort fields, so the result is always one of GameSort's values.
  const field = String(descriptor.column);
  return (descriptor.direction === "descending" ? `-${field}` : field) as GameSort;
}

interface GameTableProps {
  games: GameListItem[];
  sort: GameSort;
  onSortChange: (sort: GameSort) => void;
  /** The ids of the selected games. */
  selected: Set<number>;
  onSelectionChange: (selected: Set<number>) => void;
}

export function GameTable(props: GameTableProps) {
  const { games, sort, onSortChange, selected, onSelectionChange } = props;
  return (
    <div className={styles.scroll}>
      <Table
        className={styles.table}
        aria-label={t("games.title")}
        sortDescriptor={descriptorOf(sort)}
        onSortChange={(descriptor) => {
          onSortChange(sortOf(descriptor));
        }}
        // Checkboxes select games; clicking elsewhere in a row still opens the game.
        selectionMode="multiple"
        selectionBehavior="toggle"
        selectedKeys={selected}
        onSelectionChange={(keys: Selection) => {
          onSelectionChange(
            keys === "all" ? new Set(games.map((game) => game.id)) : new Set([...keys].map(Number)),
          );
        }}
      >
        <TableHeader>
          <Column className={classes(styles.selectColumn, styles.select)}>
            <SelectionBox />
          </Column>
          <Column id="date" allowsSorting className={classes(styles.column, styles.date)}>
            {t("games.column.date")}
          </Column>
          <Column
            id="white"
            allowsSorting
            isRowHeader
            className={classes(styles.column, styles.white)}
          >
            {t("games.column.white")}
          </Column>
          <Column id="black" allowsSorting className={classes(styles.column, styles.black)}>
            {t("games.column.black")}
          </Column>
          <Column className={classes(styles.column, styles.result)}>
            {t("games.column.result")}
          </Column>
          <Column id="eco" allowsSorting className={classes(styles.column, styles.wideOnly)}>
            {t("games.column.opening")}
          </Column>
          <Column className={classes(styles.column, styles.wideOnly)}>
            {t("games.column.timeClass")}
          </Column>
          <Column className={classes(styles.column, styles.wideOnly)}>
            {t("games.column.event")}
          </Column>
        </TableHeader>
        <TableBody items={games}>
          {(game) => (
            <Row className={styles.row} id={game.id} href={`/games/${String(game.id)}`}>
              <Cell className={classes(styles.cell, styles.select)}>
                <SelectionBox />
              </Cell>
              <Cell className={classes(styles.cell, styles.date)}>
                {formatGameDate(game.date_pgn)}
              </Cell>
              <Cell className={classes(styles.cell, styles.white)}>
                <Player
                  name={game.white}
                  elo={game.white_elo}
                  isUser={game.user_color === "white"}
                />
              </Cell>
              <Cell className={classes(styles.cell, styles.black)}>
                <Player
                  name={game.black}
                  elo={game.black_elo}
                  isUser={game.user_color === "black"}
                />
              </Cell>
              <Cell className={classes(styles.cell, styles.result)}>
                {game.result === "1/2-1/2" ? "½-½" : game.result}
              </Cell>
              <Cell className={classes(styles.cell, styles.wideOnly)}>
                {game.eco && <span className={styles.eco}>{game.eco}</span>} {game.opening}
              </Cell>
              <Cell className={classes(styles.cell, styles.wideOnly)}>
                {game.time_class === "unknown" ? "" : t(`games.timeClass.${game.time_class}`)}
              </Cell>
              <Cell className={classes(styles.cell, styles.wideOnly)}>
                {game.event}
                {game.tags.map((tag) => (
                  <span key={tag.id} className={styles.tag}>
                    {tag.name}
                  </span>
                ))}
              </Cell>
            </Row>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

/** A row's checkbox, or the header's, which selects or clears the whole page. */
function SelectionBox() {
  return (
    <CheckboxField slot="selection">
      <CheckboxButton className={styles.checkbox}>
        {({ isSelected, isIndeterminate }) => (
          <span className={styles.box} aria-hidden="true">
            {isIndeterminate ? "–" : isSelected ? "✓" : ""}
          </span>
        )}
      </CheckboxButton>
    </CheckboxField>
  );
}

function Player({ name, elo, isUser }: { name: string; elo: number | null; isUser: boolean }) {
  const label = name || t("games.unknownPlayer");
  return (
    <>
      {isUser ? <strong>{label}</strong> : label}
      {elo !== null && <span className={styles.elo}> {elo}</span>}
    </>
  );
}
