import { Route, Routes } from "react-router";

import { LoginPage, RequireAuth } from "../features/auth";
import { ReferenceGamePage, ReferencePage, SearchPage } from "../features/explorer";
import { GameListPage, GamePage, LabelsPage } from "../features/games";
import { HomePage } from "../features/home";
import { ImportPage } from "../features/imports";
import { DrillPage, GapsPage, RepertoireListPage, RepertoirePage } from "../features/repertoire";
import { SettingsPage } from "../features/settings";
import { TrainPage } from "../features/training";
import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

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
