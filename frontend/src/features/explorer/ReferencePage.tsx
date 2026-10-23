import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, Label, TextField } from "react-aria-components";
import { Link } from "react-router";

import { Select } from "../../components/Select";
import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { formatGameDate } from "../games";
import { databasesQuery, referenceGamesQuery } from "./explorer";
import styles from "./ReferencePage.module.css";

const numbers = new Intl.NumberFormat();
const PAGE = 50;

/** Reference databases (e.g. a master database) and their games, to browse and open. */
export function ReferencePage() {
  const databases = useQuery(databasesQuery);
  const { params, setParam } = useUrlParams();
  const ready = (databases.data ?? []).filter((d) => d.status === "ready");
  const chosen = ready.find((d) => String(d.id) === params.get("db")) ?? ready[0];

  return (
    <div className={styles.page}>
      <h1>{t("reference.title")}</h1>
      {databases.data && ready.length === 0 && <p className={styles.note}>{t("reference.none")}</p>}
      {ready.length > 1 && chosen && (
        <Select
          label={t("reference.database")}
          anyOption={t("reference.database")}
          options={ready.map((d) => ({ id: String(d.id), name: d.name }))}
          value={String(chosen.id)}
          onChange={(id) => {
            setParam("db", id);
          }}
        />
      )}
      {chosen && (
        <>
          <p className={styles.note}>
            {chosen.description || chosen.name} ·{" "}
            {t("reference.count", { count: numbers.format(chosen.game_count) })}
          </p>
          <Games key={chosen.id} databaseId={chosen.id} />
        </>
      )}
    </div>
  );
}

function Games({ databaseId }: { databaseId: number }) {
  const [player, setPlayer] = useState("");
  const [offset, setOffset] = useState(0);
  const filters = player.trim() ? { player: player.trim() } : {};
  const games = useQuery(referenceGamesQuery(databaseId, filters, offset));

  return (
    <section aria-label={t("reference.games")}>
      <TextField
        className={styles.field}
        value={player}
        onChange={(value) => {
          setPlayer(value);
          setOffset(0);
        }}
      >
        <Label className={styles.label}>{t("reference.player")}</Label>
        <Input className={styles.input} />
      </TextField>
      {games.isError && <p role="alert">{t("reference.loadFailed")}</p>}
      {games.data && (
        <>
          <div className={styles.scroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">{t("games.column.white")}</th>
                  <th scope="col">{t("games.column.black")}</th>
                  <th scope="col">{t("games.column.result")}</th>
                  <th scope="col">{t("games.column.date")}</th>
                  <th scope="col" className={styles.wideOnly}>
                    {t("games.column.event")}
                  </th>
                  <th scope="col" className={styles.wideOnly}>
                    ECO
                  </th>
                </tr>
              </thead>
              <tbody>
                {games.data.items.map((game) => (
                  <tr key={game.id}>
                    <td>
                      <Link to={`/reference/${String(databaseId)}/games/${String(game.id)}`}>
                        {game.white || "?"}
                      </Link>
                      {game.white_elo ? ` ${String(game.white_elo)}` : ""}
                    </td>
                    <td>
                      {game.black || "?"}
                      {game.black_elo ? ` ${String(game.black_elo)}` : ""}
                    </td>
                    <td>{game.result === "1/2-1/2" ? "½-½" : game.result}</td>
                    <td>{formatGameDate(game.date_pgn)}</td>
                    <td className={styles.wideOnly}>{game.event}</td>
                    <td className={styles.wideOnly}>{game.eco}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={styles.pager}>
            <Button
              className={styles.button}
              isDisabled={offset === 0}
              onPress={() => {
                setOffset(offset - PAGE);
              }}
            >
              {t("games.previous")}
            </Button>
            <span>
              {t("games.range", {
                first: games.data.total === 0 ? 0 : offset + 1,
                last: Math.min(offset + PAGE, games.data.total),
                total: games.data.total,
              })}
            </span>
            <Button
              className={styles.button}
              isDisabled={offset + PAGE >= games.data.total}
              onPress={() => {
                setOffset(offset + PAGE);
              }}
            >
              {t("games.next")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
