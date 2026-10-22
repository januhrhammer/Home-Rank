import { HttpResponse } from "msw";
import { expect, test } from "vitest";

import { ApiError } from "../../api/errors";
import { answerUploads } from "../../test/uploads";
import { uploadErrorMessage, uploadPgn } from "./imports";

test("uploads the file as the form field the API expects", async () => {
  const uploads = answerUploads(() => HttpResponse.json({ id: 7 }, { status: 202 }));

  const run = await uploadPgn(new File(["1. e4 e5 *"], "club.pgn"));

  expect(uploads).toEqual([{ url: "/api/v1/games/imports", fields: ["file"] }]);
  expect(run.id).toBe(7);
});

test("a refused upload is an ApiError with its status", async () => {
  answerUploads(() => new HttpResponse(null, { status: 415 }));

  await expect(uploadPgn(new File(["PK"], "games.pgn"))).rejects.toEqual(new ApiError(415));
});

test("upload errors in the user's words", () => {
  expect(uploadErrorMessage(new ApiError(413))).toBe(
    "This file is larger than the server accepts.",
  );
  expect(uploadErrorMessage(new ApiError(415))).toBe("Only PGN files (.pgn) can be imported.");
  expect(uploadErrorMessage(new ApiError(500))).toBe("The upload didn't work. Please try again.");
  expect(uploadErrorMessage(new TypeError("Failed to fetch"))).toBe(
    "The upload didn't work. Please try again.",
  );
});
