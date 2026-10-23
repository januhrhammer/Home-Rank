import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import { formatGameDate } from "../games";
import { outcomeFor } from "./moves";
import { type BotGame, gamesQuery } from "./play";
import styles from "./PlayListPage.module.css";
import { StartGameDialog } from "./StartGameDialog";

/** The user's games against bots, newest first, and a way to start one. */
export function PlayListPage() {
  const games = useQuery(gamesQuery);
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>{t("play.title")}</h1>
        <StartGameDialog />
      </div>
      <p className={styles.intro}>{t("play.intro")}</p>
      {games.isError && <p role="alert">{t("play.loadFailed")}</p>}
      {games.data?.length === 0 && <p className={styles.none}>{t("play.none")}</p>}
      <ul className={styles.list}>
        {games.data?.map((game) => (
          <li key={game.id} className={styles.item}>
            <Link className={styles.name} to={`/play/${String(game.id)}`}>
              {game.opponent_name}
            </Link>
            <span className={styles.details}>
              {[t(`play.${game.user_color}`), game.start_label, date(game)]
                .filter(Boolean)
                .join(" · ")}
            </span>
            <span className={styles.result}>{resultText(game)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function date(game: BotGame): string {
  const day = new Date(game.created_at);
  const pgn = `${String(day.getFullYear())}.${String(day.getMonth() + 1).padStart(2, "0")}.${String(day.getDate()).padStart(2, "0")}`;
  return formatGameDate(pgn);
}

function resultText(game: BotGame): string {
  const outcome = outcomeFor(game.result, game.user_color);
  return outcome === null ? t("play.result.playing") : t(`play.outcome.${outcome}`);
}
