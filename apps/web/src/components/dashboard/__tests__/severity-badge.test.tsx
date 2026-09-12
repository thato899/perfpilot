import type { Severity } from "@perfpilot/schemas/types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeverityBadge } from "../severity-badge";

describe("SeverityBadge", () => {
  it.each<Severity>(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])(
    "renders the %s label",
    (severity) => {
      render(<SeverityBadge severity={severity} />);
      expect(screen.getByText(severity)).toBeInTheDocument();
    },
  );

  it("gives CRITICAL and LOW visibly different colors", () => {
    // Not asserting exact Tailwind classes (implementation detail) — just
    // that the two ends of the severity scale don't collapse to the same
    // background, which is the whole point of the badge existing.
    render(
      <>
        <SeverityBadge severity="CRITICAL" />
        <SeverityBadge severity="LOW" />
      </>,
    );
    const critical = screen.getByText("CRITICAL");
    const low = screen.getByText("LOW");
    expect(critical.className).not.toBe(low.className);
  });
});
