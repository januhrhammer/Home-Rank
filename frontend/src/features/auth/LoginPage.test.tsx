import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { renderApp } from "../../test/render";
import { server } from "../../test/server";
import { currentUserQuery, type User } from "./currentUser";

const alice: User = { id: 1, username: "alice", email: "", is_staff: false };

/** The simulated API hands out a CSRF token and answers the login with this response. */
function loginAnswers(response: HttpResponse<User> | HttpResponse<null>) {
  server.use(
    http.get("*/api/v1/auth/csrf", () => new HttpResponse(null, { status: 204 })),
    http.post("*/api/v1/auth/login", () => response),
  );
}

async function logIn(username: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), username);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

test("logging in leads to the start page and remembers the user", async () => {
  loginAnswers(HttpResponse.json(alice));
  const { queryClient } = renderApp("/login");

  await logIn("alice", "correct horse battery staple");

  expect(await screen.findByRole("heading", { name: "Home-Rank" })).toBeInTheDocument();
  expect(queryClient.getQueryData(currentUserQuery.queryKey)).toEqual(alice);
});

test("wrong credentials show a message and stay on the page", async () => {
  loginAnswers(new HttpResponse(null, { status: 401 }));
  renderApp("/login");

  await logIn("alice", "not the right password");

  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
  expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
});

test("too many failed attempts get their own message", async () => {
  loginAnswers(new HttpResponse(null, { status: 429 }));
  renderApp("/login");

  await logIn("alice", "not the right password");

  expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed attempts");
});

test("empty fields are reported before anything is sent", async () => {
  // No answers registered: any request would make this test fail.
  renderApp("/login");

  await userEvent.setup().click(screen.getByRole("button", { name: "Log in" }));

  expect(screen.getByLabelText("Username")).toBeInvalid();
  expect(screen.getByLabelText("Password")).toBeInvalid();
});
