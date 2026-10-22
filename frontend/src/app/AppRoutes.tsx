import { Route, Routes } from "react-router";

import { LoginPage, RequireAuth } from "../features/auth";
import { GameListPage, GamePage, LabelsPage } from "../features/games";
import { HomePage } from "../features/home";
import { ImportPage } from "../features/imports";
import { SettingsPage } from "../features/settings";
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
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
