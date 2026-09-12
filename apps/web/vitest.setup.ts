import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Not using vitest's `globals: true`, so React Testing Library's usual
// auto-cleanup (which hooks into a global afterEach) never fires on its
// own — wire it up explicitly, or one test's rendered DOM leaks into the
// next and getByText starts matching duplicates.
afterEach(() => {
  cleanup();
});

// mock-api.ts persists everything to localStorage — clear it between tests
// so one test's investigation/target data can't leak into the next.
afterEach(() => {
  window.localStorage.clear();
});
