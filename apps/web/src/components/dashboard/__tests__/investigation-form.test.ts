import { expect, it } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { investigationErrorMessage, normalizeRequestPath } from "../investigation-form";

it("explains the configured concurrency and duration limits", () => {
  const concurrency = new ApiRequestError(
    "Requested concurrency exceeds the configured safety ceiling.",
    429,
    "vus_over_limit",
    { requested_vus: 10, max_virtual_users: 1 },
  );
  expect(investigationErrorMessage(concurrency)).toContain("Requested 10 simulated users");
  expect(investigationErrorMessage(concurrency)).toContain("MAX_VIRTUAL_USERS in .env");

  const duration = new ApiRequestError(
    "Requested duration exceeds the configured safety ceiling.",
    429,
    "duration_over_limit",
    { requested_seconds: 180, max_test_duration_seconds: 120 },
  );
  expect(investigationErrorMessage(duration)).toContain("180 seconds");
  expect(investigationErrorMessage(duration)).toContain("MAX_TEST_DURATION_SECONDS in .env");
});

it("normalizes a same-target URL and rejects an off-target URL or query string", () => {
  const baseUrl = "https://eduquesttutors.co.za";

  expect(normalizeRequestPath("https://eduquesttutors.co.za/login.php", baseUrl)).toBe(
    "/login.php",
  );
  expect(normalizeRequestPath("https://other.example/login.php", baseUrl)).toBeNull();
  expect(
    normalizeRequestPath("https://eduquesttutors.co.za/login.php?token=x", baseUrl),
  ).toBeNull();
  expect(normalizeRequestPath("/login.php", baseUrl)).toBe("/login.php");
});
