// Mirrors app/models/user.py User.Role (support inserted at 2; admin/super shifted).
export const ROLE_KEYS: Record<number, string> = {
  0: "user",
  1: "reseller",
  2: "support",
  3: "admin",
  4: "super_user",
};

export const ROLE_COLORS: Record<number, string> = {
  0: "default",
  1: "blue",
  2: "purple",
  3: "gold",
  4: "green",
};

// Role thresholds for permission checks — never compare against raw numbers.
export const ROLE_ADMIN = 3;
export const ROLE_SUPER = 4;
export const ROLE_VALUES = [0, 1, 2, 3, 4];

import { formatDate } from "./datetime";

export const fmtNum = (n?: number | null): string =>
  new Intl.NumberFormat("en-US").format(n ?? 0);

export const fmtToman = (n?: number | null): string => `${fmtNum(n)} تومان`;

// Calendar-aware (Jalali / Gregorian) per the global preference; see utils/datetime.
export const fmtDate = (s?: string | null): string => formatDate(s);
