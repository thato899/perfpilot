import { afterEach, describe, expect, it, vi } from "vitest";

import { buildDemoReport } from "@/lib/fixtures";
import { downloadReportCsv, reportExportCsv } from "../report-export";

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(window.URL, "createObjectURL");
  Reflect.deleteProperty(window.URL, "revokeObjectURL");
});

describe("single-run report CSV", () => {
  it("exports measurements and grounded interpretations without inventing a comparison", () => {
    const report = buildDemoReport("investigation-1");
    report.executiveSummary = '=SUM(1,2), "look here"';

    const csv = reportExportCsv(report, false);

    expect(csv).toContain('"section","item","value","unit"');
    expect(csv).toContain('"metric","p95","890","ms"');
    expect(csv).toContain('"metric","error_rate","0.008","fraction"');
    expect(csv).toContain('"hypothesis","likely_cause"');
    expect(csv).toContain('"recommendation","statement"');
    expect(csv).toContain('"\'=SUM(1,2), ""look here"""');
    expect(csv).not.toContain('"regression","previous_p95"');
    expect(reportExportCsv(report, true)).toContain('"regression","previous_p95","420","ms"');

    report.keyMetrics.peakConcurrencyTested = 1;
    const oneUserCsv = reportExportCsv(report, false);
    expect(oneUserCsv).toContain(
      '"capacity_estimate","status","not established by a one-user run"',
    );
    expect(oneUserCsv).not.toContain('"capacity_estimate","sustainable_users"');
  });

  it("starts a browser download with a report-specific filename", () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:report");
    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    downloadReportCsv(buildDemoReport("investigation-1"), false);

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(createObjectURL.mock.calls[0][0]).toBeInstanceOf(Blob);
    expect(click).toHaveBeenCalledOnce();
  });
});
