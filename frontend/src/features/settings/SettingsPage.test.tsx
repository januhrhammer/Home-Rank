import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test } from "vitest";

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

/** A simulated analysis settings API that keeps what was saved. Returns the changes received. */
function simulateAnalysisSettings(status = 200) {
  const received: unknown[] = [];
  let stored = { auto_analyse: true, inaccuracy: 10, mistake: 20, blunder: 30 };
  server.use(
    http.get("*/api/v1/analysis/settings", () => HttpResponse.json(stored)),
    http.patch("*/api/v1/analysis/settings", async ({ request }) => {
      const changes = (await request.json()) as typeof stored;
      received.push(changes);
      if (status !== 200) {
        return new HttpResponse(null, { status });
      }
      stored = { ...stored, ...changes };
      return HttpResponse.json(stored);
    }),
  );
  return received;
}

function namesSection() {
  return screen.getByRole("region", { name: "Your player names" });
}

function analysisSection() {
  return screen.getByRole("region", { name: "Engine analysis" });
}

function openSettings() {
  simulateAuth(jan, { loggedIn: true });
  renderApp("/settings");
}

beforeEach(() => {
  simulateAnalysisSettings();
});

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
  await user.click(within(namesSection()).getByRole("button", { name: "Save" }));

  expect(await within(namesSection()).findByRole("status")).toHaveTextContent(
    "Saved. Your games are being updated in the background.",
  );
  expect(received).toEqual([{ player_names: ["Uhrhammer, Jan", "  januhrhammer ", ""] }]);
  expect(names).toHaveValue("Uhrhammer, Jan\njanuhrhammer");

  // Typing again: "Saved" no longer applies.
  await user.type(names, "x");
  expect(within(namesSection()).getByRole("status")).toBeEmptyDOMElement();
});

test("a failed save says so", async () => {
  simulateSettings([]);
  server.use(http.patch("*/api/v1/settings", () => new HttpResponse(null, { status: 500 })));
  openSettings();
  const user = userEvent.setup();

  await user.type(await screen.findByRole("textbox", { name: "Player names" }), "jan");
  await user.click(within(namesSection()).getByRole("button", { name: "Save" }));

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

test("turns automatic analysis off and changes the thresholds", async () => {
  simulateSettings([]);
  const received = simulateAnalysisSettings();
  openSettings();
  const user = userEvent.setup();

  const auto = await screen.findByRole("switch", { name: "Analyse new games automatically" });
  expect(auto).toBeChecked();
  await user.click(auto);
  const blunder = screen.getByRole("textbox", { name: "Blunder" });
  await user.clear(blunder);
  await user.type(blunder, "25");
  await user.click(within(analysisSection()).getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(received).toEqual([{ auto_analyse: false, inaccuracy: 10, mistake: 20, blunder: 25 }]);
});

test("thresholds out of order are explained", async () => {
  simulateSettings([]);
  simulateAnalysisSettings(422);
  openSettings();
  const user = userEvent.setup();

  await screen.findByRole("switch", { name: "Analyse new games automatically" });
  await user.click(within(analysisSection()).getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("must lose less than a mistake");
});
