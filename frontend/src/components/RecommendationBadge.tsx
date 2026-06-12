import { CircleCheck, CircleSlash, PauseCircle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { RECOMMENDATION_LABELS } from "@/lib/strings";
import type { Recommendation } from "@/lib/types";

const ICONS: Record<Recommendation, typeof CircleCheck> = {
  proceed: CircleCheck,
  hold: PauseCircle,
  reject: CircleSlash,
};

export function RecommendationBadge({ value }: { value: Recommendation }) {
  const Icon = ICONS[value];
  return (
    <Badge variant={value}>
      <Icon className="size-3.5" />
      {RECOMMENDATION_LABELS[value]}
    </Badge>
  );
}
