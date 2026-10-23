import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { renderApp } from "../test/render";
import { simulateAuth } from "../test/server";

const alice = { id: 1, username: "alice", email: "", is_staff: false };

// The menu button only shows on narrow screens (CSS, which jsdom doesn't apply); these tests
// check what it says about the menu, which narrow screens show or hide by it.

test("the menu button opens and closes the menu", async () => {
  simulateAuth(alice, { loggedIn: true });
  renderApp("/");
  const user = userEvent.setup();

  const button = await screen.findByRole("button", { name: "Menu" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(button).toHaveAttribute("aria-controls", "site-menu");

  await user.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");

  await user.click(button);
  expect(button).toHaveAttribute("aria-expanded", "false");
});

test("following a link closes the menu", async () => {
  simulateAuth(alice, { loggedIn: true });
  renderApp("/");
  const user = userEvent.setup();

  const button = await screen.findByRole("button", { name: "Menu" });
  await user.click(button);
  await user.click(screen.getByRole("link", { name: "Settings" }));

  // Pages load when first shown; until the new one is there, the old one stays, menu and all.
  expect(await screen.findByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument();
  expect(button).toHaveAttribute("aria-expanded", "false");
});

test("visitors get no menu button, only the way in", async () => {
  simulateAuth(alice);
  renderApp("/no-such-page");

  expect(await screen.findByRole("link", { name: "Log in" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Menu" })).not.toBeInTheDocument();
});
