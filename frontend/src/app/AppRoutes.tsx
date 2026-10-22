import { Route, Routes } from "react-router";

import { LoginPage } from "../features/auth";
import { HomePage } from "../features/home";
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
        <Route index element={<HomePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
