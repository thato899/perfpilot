import type { InvestigationState } from "@perfpilot/schemas/types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InvestigationStatusBadge } from "../status-badge";

describe("InvestigationStatusBadge", () => {
  const cases: Array<[InvestigationState["status"], string]> = [
    ["planning", "Planning"],
    ["running", "Running"],
    ["investigating", "Investigating"],
    ["experimenting", "Experimenting"],
    ["reporting", "Reporting"],
    ["complete", "Complete"],
    ["failed", "Failed"],
  ];

  it.each(cases)("renders %s as %s", (status, label) => {
    render(<InvestigationStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
