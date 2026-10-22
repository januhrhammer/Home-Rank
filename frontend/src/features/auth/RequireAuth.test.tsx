import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { simulateAuth } from "../../test/server";
import { currentUserQuery, type User } from "./currentUser";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

test("visitors are sent to the login page and brought back afterwards", async () => {
  simulateAuth(alice);
  renderApp("/");

  expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();

  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), "alice");
  await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: "Log in" }));

  expect(await screen.findByRole("heading", { name: "Home-Rank" })).toBeInTheDocument();
});

test("the header shows who is logged in", async () => {
  simulateAuth(alice, { loggedIn: true });
  renderApp("/");

  expect(await screen.findByText("alice")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
});

test("logging out shows the login page and forgets the user's cached data", async () => {
  simulateAuth(alice, { loggedIn: true });
  const { queryClient } = renderApp("/");
  queryClient.setQueryData(["games"], ["a game of alice's"]); // stands in for real data

  await userEvent.setup().click(await screen.findByRole("button", { name: "Log out" }));

  expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  // The protected start page must be gone too, not just the header updated.
  expect(screen.queryByText(/turned into your personal training plan/)).not.toBeInTheDocument();
  expect(queryClient.getQueryData(["games"])).toBeUndefined();
});

test("logged-in users who open the login page go straight on", async () => {
  simulateAuth(alice, { loggedIn: true });
  renderApp("/login");

  expect(await screen.findByRole("heading", { name: "Home-Rank" })).toBeInTheDocument();
});

test("visitors see a way to log in in the header", async () => {
  renderApp("/no-such-page");

  expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
});

test("the login page doesn't link to itself", async () => {
  const { queryClient } = renderApp("/login");

  // Once the app knows nobody is logged in, the header would show the link.
  await waitFor(() => {
    expect(queryClient.getQueryData(currentUserQuery.queryKey)).toBeNull();
  });
  expect(screen.queryByRole("link", { name: "Log in" })).not.toBeInTheDocument();
});
