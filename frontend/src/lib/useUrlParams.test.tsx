import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { expect, test } from "vitest";

import { useUrlParams } from "./useUrlParams";

function Example() {
  const { params, setParam } = useUrlParams();
  const location = useLocation();
  return (
    <>
      <output>{location.search}</output>
      <button
        type="button"
        onClick={() => {
          // Two changes before React renders again: neither may get lost.
          setParam("color", "black");
          setParam("sort", "-white", ["page"]);
        }}
      >
        Both
      </button>
      <span>{params.get("color")}</span>
    </>
  );
}

test("quick changes build on each other", async () => {
  render(
    <MemoryRouter initialEntries={["/games?page=3"]}>
      <Example />
    </MemoryRouter>,
  );

  await userEvent.setup().click(screen.getByRole("button", { name: "Both" }));

  expect(screen.getByRole("status")).toHaveTextContent("?color=black&sort=-white");
});
