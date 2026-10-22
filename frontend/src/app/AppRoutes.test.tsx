import { screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { renderApp } from "../test/render";
import { SOURCE_CODE_URL } from "./config";

test("the start page shows the app name as the main heading", () => {
  renderApp("/");

  expect(screen.getByRole("heading", { level: 1, name: "Home-Rank" })).toBeInTheDocument();
});

test("unknown addresses show a not-found page with a way back", () => {
  renderApp("/no-such-page");

  expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to the start page" })).toHaveAttribute("href", "/");
});

test("every page links to the source code, as the AGPL requires", () => {
  renderApp("/no-such-page");

  expect(screen.getByRole("link", { name: "Source code" })).toHaveAttribute(
    "href",
    SOURCE_CODE_URL,
  );
});
