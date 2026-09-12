import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Mirrors tsconfig.json's "paths" — Vitest doesn't read tsconfig path
// mapping on its own, so both alias sets are kept in sync manually.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@perfpilot/schemas": fileURLToPath(
        new URL("../../packages/schemas/typescript", import.meta.url),
      ),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: true,
  },
});
