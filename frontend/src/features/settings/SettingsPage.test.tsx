import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server, simulateAuth } from "../../test/server";
import type { User } from "../auth";
import type { SettingsChanges } from "./settings";

const jan: User = { id: 1, username: "jan", email: "", is_staff: false };

/**
 * A simulated settings API that keeps what was saved and tidies names like the server does
 * (trimmed, empty lines dropped). Returns the changes it received.
 */
function simulateSettings(playerNames: string[]) {
  const received: SettingsChanges[] = [];
  let names = playerNames;
  server.use(
    http.get("*/api/v1/settings", () => HttpResponse.json({ player_names: names })),
    http.patch("*/api/v1/settings", async ({ request }) => {
      const changes = (await request.json()) as SettingsChanges;
      received.push(changes);
      names = (changes.player_names ?? names).map((name) => name.trim()).filter(Boolean);
      return HttpResponse.json({ player_names: names });
    }),
  );
  return received;
}

function openSettings() {
  simulateAuth(jan, { loggedIn: true });
  renderApp("/settings");
}

test("shows the player names, one per line", async () => {
  simulateSettings(["Uhrhammer, Jan", "januhrhammer"]);
  openSettings();

  expect(await screen.findByRole("textbox", { name: "Player names" })).toHaveValue(
    "Uhrhammer, Jan\njanuhrhammer",
  );
});

test("saves the names and shows them as the server keeps them", async () => {
  const received = simulateSettings(["Uhrhammer, Jan"]);
  openSettings();
  const user = userEvent.setup();
  const names = await screen.findByRole("textbox", { name: "Player names" });

  await user.type(names, "\n  januhrhammer \n");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Saved. Your games are being updated in the background.",
  );
  expect(received).toEqual([{ player_names: ["Uhrhammer, Jan", "  januhrhammer ", ""] }]);
  expect(names).toHaveValue("Uhrhammer, Jan\njanuhrhammer");

  // Typing again: "Saved" no longer applies.
  await user.type(names, "x");
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});

test("a failed save says so", async () => {
  simulateSettings([]);
  server.use(http.patch("*/api/v1/settings", () => new HttpResponse(null, { status: 500 })));
  openSettings();
  const user = userEvent.setup();

  await user.type(await screen.findByRole("textbox", { name: "Player names" }), "jan");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Saving didn't work.");
});

test("settings that can't be loaded say so", async () => {
  server.use(http.get("*/api/v1/settings", () => new HttpResponse(null, { status: 500 })));
  openSettings();

  expect(await screen.findByRole("alert")).toHaveTextContent("couldn't be loaded");
});

test("the header leads to the settings", async () => {
  simulateSettings([]);
  simulateAuth(jan, { loggedIn: true });
  renderApp("/games-that-dont-exist");
  const user = userEvent.setup();

  await user.click(await screen.findByRole("link", { name: "Settings" }));

  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
});
