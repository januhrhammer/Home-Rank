import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { AppRoutes } from "../app/AppRoutes";

/**
 * Renders the whole app at an address, with a fresh cache, as a user would see it. Failed
 * requests aren't retried, so tests about errors don't wait for retries.
 */
export function renderApp(address: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[address]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { queryClient };
}
