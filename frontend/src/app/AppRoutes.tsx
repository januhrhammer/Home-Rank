import { type ComponentType, lazy } from "react";
import { Route, Routes } from "react-router";

import { LoginPage, RequireAuth } from "../features/auth";
import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

/** Set while reloading because a page's files didn't load (lazyPage). */
const RELOADED = "home-rank:reloaded-for-update";

/**
 * A page that is downloaded when it is first shown, not with the app: the app itself stays
 * small, and a page's code (the board, the chess rules, its tables) comes with the page. The
 * layout shows the header meanwhile (Layout's Suspense). `load` imports the page's feature.
 */
function lazyPage<Name extends string>(
  load: () => Promise<Record<Name, ComponentType>>,
  name: Name,
) {
  return lazy(async () => {
    try {
      const page = { default: (await load())[name] };
      sessionStorage.removeItem(RELOADED);
      return page;
    } catch (error) {
      // After an update, a tab opened before it asks for the old version's files, which are
      // gone: load the new version instead. Only once, in case the files are missing for
      // another reason (then the error stands).
      if (sessionStorage.getItem(RELOADED) === null) {
        sessionStorage.setItem(RELOADED, "1");
        window.location.reload();
        return new Promise<never>(() => undefined); // the reload replaces the page
      }
      throw error;
    }
  });
}

const HomePage = lazyPage(() => import("../features/home"), "HomePage");
const GameListPage = lazyPage(() => import("../features/games"), "GameListPage");
const GamePage = lazyPage(() => import("../features/games"), "GamePage");
const LabelsPage = lazyPage(() => import("../features/games"), "LabelsPage");
const ImportPage = lazyPage(() => import("../features/imports"), "ImportPage");
const SettingsPage = lazyPage(() => import("../features/settings"), "SettingsPage");
const TrainPage = lazyPage(() => import("../features/training"), "TrainPage");
const RepertoireListPage = lazyPage(() => import("../features/repertoire"), "RepertoireListPage");
const RepertoirePage = lazyPage(() => import("../features/repertoire"), "RepertoirePage");
const DrillPage = lazyPage(() => import("../features/repertoire"), "DrillPage");
const GapsPage = lazyPage(() => import("../features/repertoire"), "GapsPage");
const SearchPage = lazyPage(() => import("../features/explorer"), "SearchPage");
const ReferencePage = lazyPage(() => import("../features/explorer"), "ReferencePage");
const ReferenceGamePage = lazyPage(() => import("../features/explorer"), "ReferenceGamePage");

/**
 * Every page of the app. Kept apart from the router itself, so tests can render it in a
 * MemoryRouter at any address.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="login" element={<LoginPage />} />
        {/* Pages for logged-in users only. */}
        <Route element={<RequireAuth />}>
          <Route index element={<HomePage />} />
          <Route path="games" element={<GameListPage />} />
          <Route path="games/:gameId" element={<GamePage />} />
          <Route path="labels" element={<LabelsPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="train" element={<TrainPage />} />
          <Route path="repertoires" element={<RepertoireListPage />} />
          <Route path="repertoires/:repertoireId" element={<RepertoirePage />} />
          <Route path="repertoires/:repertoireId/drill" element={<DrillPage />} />
          <Route path="repertoires/:repertoireId/gaps" element={<GapsPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="reference" element={<ReferencePage />} />
          <Route path="reference/:databaseId/games/:gameId" element={<ReferenceGamePage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
