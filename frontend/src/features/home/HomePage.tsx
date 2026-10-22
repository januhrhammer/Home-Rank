import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";

/** The standard starting position, in FEN notation. */
const START_POSITION = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export function HomePage() {
  return (
    <>
      <h1>{t("app.name")}</h1>
      <p>{t("app.tagline")}</p>
      <Board fen={START_POSITION} />
    </>
  );
}
