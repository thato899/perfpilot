import type { Severity } from "@perfpilot/schemas/types";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Not shadcn's default variant set (default/secondary/destructive/outline) —
// severity needs its own five-way color scale, so this maps straight to
// Tailwind classes rather than fighting the Badge variant prop for a shape
// it wasn't designed for.
const SEVERITY_CLASSES: Record<Severity, string> = {
  CRITICAL: "bg-red-600 text-white dark:bg-red-500",
  HIGH: "bg-orange-500 text-white dark:bg-orange-500",
  MEDIUM: "bg-amber-400 text-black dark:bg-amber-400",
  LOW: "bg-blue-500 text-white dark:bg-blue-500",
  INFO: "bg-slate-400 text-white dark:bg-slate-500",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={cn(SEVERITY_CLASSES[severity], "font-medium")}>{severity}</Badge>;
}
