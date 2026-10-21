import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "./App";

test("shows the app name as the main heading", () => {
  render(<App />);

  expect(screen.getByRole("heading", { level: 1, name: "Home-Rank" })).toBeInTheDocument();
});
