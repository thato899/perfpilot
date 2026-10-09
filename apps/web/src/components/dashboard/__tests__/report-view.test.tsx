import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { buildDemoReport } from "@/lib/fixtures";
import { ReportView } from "../report-view";

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(window.URL, "createObjectURL");
  Reflect.deleteProperty(window.URL, "revokeObjectURL");
});

it("downloads the report CSV for a completed first run without a comparison", async () => {
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

  render(<ReportView report={buildDemoReport("first-run")} hasPreviousRun={false} />);
  await userEvent.setup().click(screen.getByRole("button", { name: "Download report CSV" }));

  expect(createObjectURL).toHaveBeenCalledOnce();
  expect(click).toHaveBeenCalledOnce();
  expect(
    screen.getByText("No separate previous run is linked to this result."),
  ).toBeInTheDocument();
});

it("states when a degraded run has no supported causal analysis", () => {
  const report = buildDemoReport("degraded-run");
  report.bottleneckAnalysis = [];

  render(<ReportView report={report} hasPreviousRun={false} />);

  expect(screen.getByText("Cause not established")).toBeInTheDocument();
  expect(screen.getByText(/Collect HTTP failure status codes/)).toBeInTheDocument();
});
