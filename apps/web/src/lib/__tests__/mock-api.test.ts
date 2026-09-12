/**
 * Tests for the mock API seam (src/lib/mock-api.ts). This is the module a
 * real `apps/api` wiring will eventually replace (see the file's own header
 * comment and apps/web/README.md's "Not yet done" section) — pinning its
 * behavior here means that swap is a diff against a known-good contract,
 * not a leap of faith.
 */
import type { ExpectedTraffic } from "@perfpilot/schemas/types";
import { describe, expect, it } from "vitest";

import {
  advanceInvestigation,
  createInvestigation,
  createTarget,
  ensureDemoTargetSeeded,
  getInvestigation,
  getReport,
  listTargets,
} from "../mock-api";

const EXPECTED_TRAFFIC: ExpectedTraffic = {
  normalConcurrentUsers: 100,
  peakConcurrentUsers: 1000,
  peakDescription: "flash sale",
};

describe("targets", () => {
  it("starts empty", async () => {
    await expect(listTargets()).resolves.toEqual([]);
  });

  it("creates a target and lists it back", async () => {
    const created = await createTarget({
      name: "Test app",
      baseUrl: "https://example.test",
      authorizationConfirmed: true,
      authorizationConfirmedBy: "thato",
    });

    expect(created.id).toMatch(/^tgt_/);
    expect(created.authorizationConfirmed).toBe(true);
    await expect(listTargets()).resolves.toEqual([created]);
  });

  it("refuses to create a target without authorization confirmation", async () => {
    // Mirrors the real API's rejection per api-contract.md — no "confirm
    // later" state exists, per mock-api.ts's own comment.
    await expect(
      createTarget({
        name: "Unconfirmed app",
        baseUrl: "https://example.test",
        authorizationConfirmed: false,
        authorizationConfirmedBy: "thato",
      }),
    ).rejects.toThrow(/authorizationConfirmed must be true/);
    await expect(listTargets()).resolves.toEqual([]);
  });

  it("ensureDemoTargetSeeded is idempotent", async () => {
    const first = await ensureDemoTargetSeeded();
    const second = await ensureDemoTargetSeeded();
    expect(second).toEqual(first);
    await expect(listTargets()).resolves.toHaveLength(1);
  });
});

describe("investigations", () => {
  it("getInvestigation rejects an unknown id", async () => {
    await expect(getInvestigation("inv_does_not_exist")).rejects.toThrow(/not found/);
  });

  it("creates an investigation in planning status with no report yet", async () => {
    const target = await ensureDemoTargetSeeded();
    const investigation = await createInvestigation({
      targetId: target.id,
      objective: "determine_capacity",
      expectedTraffic: EXPECTED_TRAFFIC,
    });

    expect(investigation.status).toBe("planning");
    expect(investigation.findings).toEqual([]);
    await expect(getInvestigation(investigation.investigationId)).resolves.toEqual(investigation);
    await expect(getReport(investigation.investigationId)).resolves.toBeNull();
  });

  it("advances tick by tick through to completion, producing a report", async () => {
    const target = await ensureDemoTargetSeeded();
    const investigation = await createInvestigation({
      targetId: target.id,
      objective: "determine_capacity",
      expectedTraffic: EXPECTED_TRAFFIC,
    });

    let current = investigation;
    const statusesSeen: string[] = [current.status];
    // DEMO_TICKS has 8 entries (see fixtures.ts) — advancing 8 times must
    // reach "complete" with a report; a 9th call must be a no-op, not an error.
    for (let i = 0; i < 8; i++) {
      current = await advanceInvestigation(current.investigationId);
      statusesSeen.push(current.status);
    }

    expect(current.status).toBe("complete");
    expect(statusesSeen).toContain("investigating"); // the anomaly stage
    expect(statusesSeen).toContain("experimenting"); // the follow-up test
    expect(current.findings).toHaveLength(1);
    expect(current.hypotheses[0]?.status).toBe("supported");

    const report = await getReport(current.investigationId);
    expect(report).not.toBeNull();
    expect(report?.investigationId).toBe(current.investigationId);

    // Advancing a completed investigation further doesn't throw or regress its state.
    const afterEnd = await advanceInvestigation(current.investigationId);
    expect(afterEnd.status).toBe("complete");
  });

  it("surfaces the finding/hypothesis only once the anomaly tick is reached", async () => {
    const target = await ensureDemoTargetSeeded();
    const investigation = await createInvestigation({
      targetId: target.id,
      objective: "determine_capacity",
      expectedTraffic: EXPECTED_TRAFFIC,
    });

    // First tick (ramping to 10 users) — no anomaly yet.
    const afterFirstTick = await advanceInvestigation(investigation.investigationId);
    expect(afterFirstTick.findings).toEqual([]);
    expect(afterFirstTick.status).toBe("running");
  });
});
