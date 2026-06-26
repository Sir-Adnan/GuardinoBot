export const ROLE_KEYS: Record<number, string> = {
  0: "user",
  1: "reseller",
  2: "admin",
  3: "super_user",
};

export const ROLE_COLORS: Record<number, string> = {
  0: "default",
  1: "blue",
  2: "gold",
  3: "green",
};

import { formatDate } from "./datetime";

export const fmtNum = (n?: number | null): string =>
  new Intl.NumberFormat("en-US").format(n ?? 0);

export const fmtToman = (n?: number | null): string => `${fmtNum(n)} تومان`;

// Calendar-aware (Jalali / Gregorian) per the global preference; see utils/datetime.
export const fmtDate = (s?: string | null): string => formatDate(s);
