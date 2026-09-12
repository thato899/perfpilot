import type { InvestigationState } from "@perfpilot/schemas/types";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_CLASSES: Record<InvestigationState["status"], string> = {
  planning: "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100",
  running: "bg-blue-500 text-white",
  investigating: "bg-amber-500 text-black",
  experimenting: "bg-purple-500 text-white",
  reporting: "bg-indigo-500 text-white",
  complete: "bg-green-600 text-white",
  failed: "bg-red-600 text-white",
};

const STATUS_LABELS: Record<InvestigationState["status"], string> = {
  planning: "Planning",
  running: "Running",
  investigating: "Investigating",
  experimenting: "Experimenting",
  reporting: "Reporting",
  complete: "Complete",
  failed: "Failed",
};

export function InvestigationStatusBadge({ status }: { status: InvestigationState["status"] }) {
  return (
    <Badge className={cn(STATUS_CLASSES[status], "font-medium")}>{STATUS_LABELS[status]}</Badge>
  );
}
