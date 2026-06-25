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

export const fmtNum = (n?: number | null): string =>
  new Intl.NumberFormat("en-US").format(n ?? 0);

export const fmtToman = (n?: number | null): string => `${fmtNum(n)} تومان`;

export const fmtDate = (s?: string | null): string => {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("fa-IR");
  } catch {
    return s;
  }
};
