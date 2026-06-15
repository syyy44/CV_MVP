import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium leading-5 transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-muted text-secondary-foreground",
        outline: "border-border bg-card text-muted-foreground",
        proceed: "border-proceed/20 bg-proceed/10 text-proceed",
        hold: "border-hold/20 bg-hold/10 text-hold",
        reject: "border-reject/20 bg-reject/10 text-reject",
        info: "border-primary/20 bg-primary/10 text-primary",
        warn: "border-hold/20 bg-hold/10 text-hold",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
