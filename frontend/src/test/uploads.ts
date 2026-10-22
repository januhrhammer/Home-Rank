import { vi } from "vitest";

/**
 * Answers uploads (POST requests with multipart form data) with `answer`, and records what was
 * sent: the address and the names of the form's fields.
 *
 * MSW can't be used for uploads here. In the test environment the browser parts are jsdom's
 * while requests are sent by Node, and Vitest's conversion between the two loses the files'
 * contents (they arrive empty, named "blob"; vitest 5.0.5, jsdom 30.1.3). So an upload is
 * answered before it is sent, and only its shape can be checked. That the file itself arrives
 * is checked in a real browser, by the end-to-end tests.
 */
export function answerUploads(answer: () => Response) {
  const sent: { url: string; fields: string[] }[] = [];
  const realFetch = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const request = new Request(input, init);
    if (!request.headers.get("Content-Type")?.startsWith("multipart/form-data")) {
      return realFetch(request);
    }
    const body = await request.text();
    // Each field's part starts with: Content-Disposition: form-data; name="file"; filename=…
    const fields = [...body.matchAll(/; name="([^"]+)"/g)].map((match) => match[1] ?? "");
    sent.push({ url: new URL(request.url).pathname, fields });
    return answer();
  });
  return sent;
}
