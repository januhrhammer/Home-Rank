import { useQuery } from "@tanstack/react-query";
import type { Piece } from "chessops/types";
import { createElement, useState } from "react";
import {
  Button,
  Input,
  Label,
  RadioButton,
  RadioField,
  RadioGroup,
  TextField,
} from "react-aria-components";
import { Link } from "react-router";

import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { formatGameDate, useNotation, withFigurines } from "../games";
import { StartGameDialog } from "../play";
import { mySearchQuery, referenceSearchQuery, type Source } from "./explorer";
import { ExplorerPanel } from "./ExplorerPanel";
import { EMPTY_BOARD, fullFen, isLegalPosition, putPiece, readFen, START_BOARD } from "./position";
import styles from "./SearchPage.module.css";

const ROLES = ["king", "queen", "rook", "bishop", "knight", "pawn"] as const;
const COLORS = ["white", "black"] as const;
type Tool = Piece | "remove" | null;

/** Set up a position (or come from a game) and find the games that reached it. */
export function SearchPage() {
  const { params, setParam } = useUrlParams();
  const start = readFen(params.get("fen") ?? "") ?? { board: START_BOARD, turn: "white" as const };
  const [board, setBoard] = useState(start.board);
  const [turn, setTurn] = useState<"white" | "black">(start.turn);
  const [tool, setTool] = useState<Tool>(null);
  const [source, setSource] = useState<Source>({ kind: "mine" });
  const [notation] = useNotation();
  const fen = fullFen(board, turn);
  const legal = isLegalPosition(fen);

  const update = (nextBoard: string, nextTurn: "white" | "black") => {
    setBoard(nextBoard);
    setTurn(nextTurn);
    setParam("fen", fullFen(nextBoard, nextTurn));
  };

  return (
    <div className={styles.page}>
      <h1>{t("search.title")}</h1>
      <div className={styles.layout}>
        <div className={styles.setup}>
          <Board
            fen={board}
            label={t("search.board")}
            editable={{
              onChange: (next) => {
                update(next, turn);
              },
              onSquare: (square) => {
                if (tool !== null) {
                  update(putPiece(board, square, tool === "remove" ? null : tool), turn);
                }
              },
            }}
          />
          <Palette tool={tool} onTool={setTool} />
          <div className={styles.controls}>
            <RadioGroup
              className={styles.turn}
              orientation="horizontal"
              value={turn}
              onChange={(value) => {
                update(board, value as "white" | "black");
              }}
            >
              <Label className={styles.label}>{t("search.toMove")}</Label>
              {COLORS.map((color) => (
                <RadioField key={color} value={color}>
                  <RadioButton className={styles.radio}>{t(`analysis.${color}`)}</RadioButton>
                </RadioField>
              ))}
            </RadioGroup>
            <Button
              className={styles.button}
              onPress={() => {
                update(START_BOARD, "white");
              }}
            >
              {t("search.start")}
            </Button>
            <Button
              className={styles.button}
              onPress={() => {
                update(EMPTY_BOARD, turn);
              }}
            >
              {t("search.clear")}
            </Button>
            {legal && (
              <StartGameDialog
                startFen={fen}
                side={turn}
                triggerLabel={t("play.newFrom")}
                triggerClassName={styles.button}
              />
            )}
          </div>
          <FenField
            fen={fen}
            onFen={(read) => {
              update(read.board, read.turn);
            }}
          />
        </div>
        <div className={styles.results}>
          {legal ? (
            <>
              <ExplorerPanel
                fen={fen}
                source={source}
                onSourceChange={setSource}
                formatMove={(san) => (notation === "figurines" ? withFigurines(san) : san)}
              />
              <Results key={`${fen} ${JSON.stringify(source)}`} fen={fen} source={source} />
            </>
          ) : (
            <p role="alert">{t("search.illegal")}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function Palette({ tool, onTool }: { tool: Tool; onTool: (tool: Tool) => void }) {
  return (
    <div className={styles.palette} role="group" aria-label={t("search.palette")}>
      {COLORS.flatMap((color) =>
        ROLES.map((role) => {
          const chosen =
            tool !== null && tool !== "remove" && tool.color === color && tool.role === role;
          return (
            <Button
              key={`${color}-${role}`}
              className={`${styles.tool ?? ""} cg-wrap`}
              aria-label={t(`search.piece.${color}`, { piece: t(`search.role.${role}`) })}
              aria-pressed={chosen}
              onPress={() => {
                onTool(chosen ? null : { color, role });
              }}
            >
              {/* chessground's piece images are styled on <piece> elements. */}
              {createElement("piece", { className: `${color} ${role}` })}
            </Button>
          );
        }),
      )}
      <Button
        className={styles.tool}
        aria-pressed={tool === "remove"}
        onPress={() => {
          onTool(tool === "remove" ? null : "remove");
        }}
      >
        {t("search.remove")}
      </Button>
    </div>
  );
}

function FenField({
  fen,
  onFen,
}: {
  fen: string;
  onFen: (read: { board: string; turn: "white" | "black" }) => void;
}) {
  const [text, setText] = useState(fen);
  const [invalid, setInvalid] = useState(false);
  const [last, setLast] = useState(fen);
  if (fen !== last) {
    // The board changed: show its FEN (state adjusted while rendering, as React suggests).
    setLast(fen);
    setText(fen);
  }
  return (
    <TextField
      className={styles.fen}
      value={text}
      onChange={(value) => {
        setText(value);
        const read = readFen(value);
        setInvalid(read === null);
        if (read) {
          onFen(read);
        }
      }}
      isInvalid={invalid}
    >
      <Label className={styles.label}>{t("search.fen")}</Label>
      <Input className={styles.input} spellCheck={false} />
    </TextField>
  );
}

function Results({ fen, source }: { fen: string; source: Source }) {
  return source.kind === "mine" ? (
    <MyResults fen={fen} />
  ) : (
    <ReferenceResults fen={fen} databaseId={source.databaseId} />
  );
}

function MyResults({ fen }: { fen: string }) {
  const [page, setPage] = useState(1);
  const query = useQuery(mySearchQuery(fen, page));
  if (!query.data) {
    return query.isError ? <p role="alert">{t("search.loadFailed")}</p> : null;
  }
  return (
    <FoundGames
      games={query.data.items}
      total={query.data.total}
      page={page}
      onPage={setPage}
      linkOf={(id) => `/games/${String(id)}`}
    />
  );
}

function ReferenceResults({ fen, databaseId }: { fen: string; databaseId: number }) {
  const [page, setPage] = useState(1);
  const query = useQuery(referenceSearchQuery(databaseId, fen, page));
  if (!query.data) {
    return query.isError ? <p role="alert">{t("search.loadFailed")}</p> : null;
  }
  if (query.data.too_common) {
    return <p className={styles.note}>{t("search.tooCommon")}</p>;
  }
  return (
    <FoundGames
      games={query.data.items}
      total={query.data.total}
      page={page}
      onPage={setPage}
      linkOf={(id) => `/reference/${String(databaseId)}/games/${String(id)}`}
    />
  );
}

interface FoundGame {
  id: number;
  white: string;
  black: string;
  result: string;
  date_pgn: string;
  event: string;
}

function FoundGames({
  games,
  total,
  page,
  onPage,
  linkOf,
}: {
  games: FoundGame[];
  total: number;
  page: number;
  onPage: (page: number) => void;
  linkOf: (id: number) => string;
}) {
  const pages = Math.max(1, Math.ceil(total / 50));
  if (total === 0) {
    return null; // the explorer above says that no game reached the position
  }
  return (
    <section aria-labelledby="found-heading">
      <h2 id="found-heading" className={styles.heading}>
        {t("search.found", { count: total })}
      </h2>
      <ul className={styles.list}>
        {games.map((game) => (
          <li key={game.id}>
            <Link to={linkOf(game.id)}>
              {game.white || "?"} – {game.black || "?"}
            </Link>{" "}
            <span className={styles.meta}>
              {[
                game.result === "1/2-1/2" ? "½-½" : game.result,
                formatGameDate(game.date_pgn),
                game.event,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </li>
        ))}
      </ul>
      {pages > 1 && (
        <div className={styles.pager}>
          <Button
            className={styles.button}
            isDisabled={page === 1}
            onPress={() => {
              onPage(page - 1);
            }}
          >
            {t("games.previous")}
          </Button>
          <span>{t("search.page", { page, pages })}</span>
          <Button
            className={styles.button}
            isDisabled={page >= pages}
            onPress={() => {
              onPage(page + 1);
            }}
          >
            {t("games.next")}
          </Button>
        </div>
      )}
    </section>
  );
}
