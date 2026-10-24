import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { useKeyboard } from "./useKeyboard";

function Page({ onRight }: { onRight: () => void }) {
  useKeyboard({ ArrowRight: onRight });
  return (
    <>
      <input aria-label="Name" />
      <input type="checkbox" aria-label="Figurines" />
      <input type="radio" aria-label="White" />
    </>
  );
}

test("page keys work, also on a switch, but not while typing or choosing a radio", async () => {
  const onRight = vi.fn();
  render(<Page onRight={onRight} />);
  const user = userEvent.setup();

  await user.keyboard("{ArrowRight}");
  await user.click(screen.getByRole("checkbox", { name: "Figurines" }));
  await user.keyboard("{ArrowRight}");
  expect(onRight).toHaveBeenCalledTimes(2);

  await user.click(screen.getByRole("textbox", { name: "Name" }));
  await user.keyboard("{ArrowRight}");
  await user.click(screen.getByRole("radio", { name: "White" }));
  await user.keyboard("{ArrowRight}");
  expect(onRight).toHaveBeenCalledTimes(2);
});
