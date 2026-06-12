import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { SUB_SCORE_LABELS } from "@/lib/strings";
import type { CandidateSubScores } from "@/lib/types";

function barColor(value: number): string {
  if (value >= 75) return "hsl(142 71% 45%)";
  if (value >= 55) return "hsl(38 92% 50%)";
  return "hsl(0 72% 51%)";
}

export function ScoreBreakdown({ subScores }: { subScores: CandidateSubScores }) {
  const data = (Object.keys(SUB_SCORE_LABELS) as (keyof CandidateSubScores)[]).map(
    (key) => ({
      key,
      label: SUB_SCORE_LABELS[key],
      value: subScores[key],
    }),
  );

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 34)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 36, bottom: 4, left: 8 }}
        barCategoryGap={8}
      >
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="label"
          width={104}
          tick={{ fill: "hsl(215 20% 65%)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "hsl(217 33% 17% / 0.4)" }}
          contentStyle={{
            background: "hsl(222 44% 8%)",
            border: "1px solid hsl(215 28% 20%)",
            borderRadius: 8,
            fontSize: 12,
            color: "hsl(210 40% 98%)",
          }}
          formatter={(value: number) => [`${value} / 100`, "得分"]}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} label={{
          position: "right",
          fill: "hsl(210 40% 90%)",
          fontSize: 12,
        }}>
          {data.map((entry) => (
            <Cell key={entry.key} fill={barColor(entry.value)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
