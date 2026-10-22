import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components, paths } from "../../api/schema";

export type GameListItem = components["schemas"]["GameListItem"];
export type Game = components["schemas"]["GameOut"];
export type NamedRef = components["schemas"]["NamedRef"];
export type GameListQuery = NonNullable<paths["/api/v1/games"]["get"]["parameters"]["query"]>;
export type GameSort = NonNullable<GameListQuery["sort"]>;

/** The start of every games query's key: invalidating it refreshes all lists and games. */
export const GAMES_KEY = ["games"] as const;

export const PAGE_SIZE = 50;
export const DEFAULT_SORT: GameSort = "-date";

const SORTS: readonly GameSort[] = [
  "date", "-date", "white", "-white", "black", "-black",
  "white_elo", "-white_elo", "black_elo", "-black_elo", "eco", "-eco",
  "imported_at", "-imported_at",
]; // prettier-ignore
const COLORS = ["white", "black"] as const;
const OUTCOMES = ["win", "draw", "loss"] as const;
const TIME_CLASSES = [
  "bullet",
  "blitz",
  "rapid",
  "classical",
  "correspondence",
  "unknown",
] as const;

/** One of the allowed values, or undefined: a hand-edited address shouldn't break the page. */
function oneOf<T extends string>(allowed: readonly T[], value: string | null): T | undefined {
  return allowed.find((candidate) => candidate === value);
}

function id(value: string | null): number | undefined {
  return value !== null && /^\d+$/.test(value) ? Number(value) : undefined;
}

function text(value: string | null): string | undefined {
  return value?.trim() || undefined;
}

/** The page number in the address, counting from 1. */
export function pageOf(params: URLSearchParams): number {
  return id(params.get("page")) ?? 1;
}

/**
 * The API query for the game list in the address, e.g. /games?outcome=loss&page=2. The address
 * holds the filters, so a filtered list can be bookmarked and the back button works.
 */
export function listQuery(params: URLSearchParams): GameListQuery {
  return {
    player: text(params.get("player")),
    color: oneOf(COLORS, params.get("color")),
    outcome: oneOf(OUTCOMES, params.get("outcome")),
    time_class: oneOf(TIME_CLASSES, params.get("time_class")),
    date_from: text(params.get("date_from")),
    date_to: text(params.get("date_to")),
    eco: text(params.get("eco")),
    opening: text(params.get("opening")),
    tag: id(params.get("tag")),
    collection: id(params.get("collection")),
    import_run: id(params.get("import_run")),
    sort: oneOf(SORTS, params.get("sort")) ?? DEFAULT_SORT,
    limit: PAGE_SIZE,
    offset: (pageOf(params) - 1) * PAGE_SIZE,
  };
}

export async function fetchGames(query: GameListQuery) {
  const { data, response } = await api.GET("/api/v1/games", { params: { query } });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

export function gamesQuery(query: GameListQuery) {
  return queryOptions({
    queryKey: [...GAMES_KEY, query],
    queryFn: () => fetchGames(query),
    // Keep showing the current page while the next one loads, instead of an empty table.
    placeholderData: keepPreviousData,
  });
}

export function useGames(query: GameListQuery) {
  return useQuery(gamesQuery(query));
}

async function fetchNamed(path: "/api/v1/tags" | "/api/v1/collections"): Promise<NamedRef[]> {
  const { data, response } = await api.GET(path, { params: { query: { limit: 100 } } });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data.items;
}

export const tagsQuery = queryOptions({
  queryKey: ["tags"],
  queryFn: () => fetchNamed("/api/v1/tags"),
});

export const collectionsQuery = queryOptions({
  queryKey: ["collections"],
  queryFn: () => fetchNamed("/api/v1/collections"),
});

export async function fetchGame(gameId: number): Promise<Game> {
  const { data, response } = await api.GET("/api/v1/games/{game_id}", {
    params: { path: { game_id: gameId } },
  });
  if (data === undefined) {
    throw new ApiError(response.status);
  }
  return data;
}

export function gameQuery(gameId: number) {
  return queryOptions({ queryKey: [...GAMES_KEY, gameId], queryFn: () => fetchGame(gameId) });
}
