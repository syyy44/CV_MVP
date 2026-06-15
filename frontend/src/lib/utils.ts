import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("zh-CN").format(value);
}

const TRAILING_ZH_PUNCT = /[。．.;；,，:：]+$/u;

/** Join parallel Chinese clauses without duplicating sentence punctuation. */
export function joinZhClauses(items: string[], separator = "；"): string {
  return items
    .map((item) => item.trim().replace(TRAILING_ZH_PUNCT, ""))
    .filter(Boolean)
    .join(separator);
}
