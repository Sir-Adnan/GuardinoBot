// Calendar-aware date formatting using the built-in Intl API (no dependency).
// "jalali" → Persian (Shamsi) calendar; "gregorian" → Gregorian. A module-level
// preference (mirrored in localStorage) lets the plain `formatDate`/`fmtDate`
// helpers reflect the user's choice; the header toggle updates it via
// `setCalendarPref`, and pages re-render through the layout so dates refresh live.

export type Calendar = "jalali" | "gregorian";

const LOCALE: Record<Calendar, string> = {
  jalali: "fa-IR-u-ca-persian",
  gregorian: "en-US-u-ca-gregory",
};

let _cal: Calendar =
  (typeof localStorage !== "undefined" &&
    (localStorage.getItem("calendar") as Calendar)) ||
  "jalali";

export const getCalendarPref = (): Calendar => _cal;

export const setCalendarPref = (c: Calendar): void => {
  _cal = c;
  try {
    localStorage.setItem("calendar", c);
  } catch {
    /* ignore */
  }
};

export interface DateOpts {
  time?: boolean; // include hour:minute (default true)
  cal?: Calendar; // override the global preference
}

export function formatDate(
  value?: string | number | Date | null,
  opts: DateOpts = {},
): string {
  if (value === null || value === undefined || value === "") return "—";
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const cal = opts.cal ?? _cal;
  const fmt: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(opts.time === false ? {} : { hour: "2-digit", minute: "2-digit" }),
  };
  try {
    return new Intl.DateTimeFormat(LOCALE[cal], fmt).format(d);
  } catch {
    return d.toLocaleString();
  }
}

// Date-only (no time), handy for table cells / report ranges.
export const formatDay = (
  value?: string | number | Date | null,
  cal?: Calendar,
): string => formatDate(value, { time: false, cal });
