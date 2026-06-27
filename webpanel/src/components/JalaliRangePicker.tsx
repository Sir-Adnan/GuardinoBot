import { useState } from "react";
import { Button, Popover, Select, Space, Typography } from "antd";
import { CalendarOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useTranslation } from "react-i18next";
import {
  J_MONTHS,
  jalaaliMonthLength,
  toGregorian,
  toJalaali,
} from "../utils/jalali";
import { formatDay } from "../utils/datetime";

const { Text } = Typography;

interface JParts {
  y: number;
  m: number;
  d: number;
}

const dayjsToJ = (d: Dayjs): JParts => {
  const j = toJalaali(d.year(), d.month() + 1, d.date());
  return { y: j.jy, m: j.jm, d: j.jd };
};

const jToDayjs = (p: JParts): Dayjs => {
  const g = toGregorian(p.y, p.m, p.d);
  return dayjs(new Date(g.gy, g.gm - 1, g.gd));
};

/**
 * Dependency-free Shamsi (Jalali) date-range picker. Edits dates with
 * year/month/day Selects in the Persian calendar but emits Gregorian Dayjs
 * values, so it's a drop-in for AntD's <RangePicker> on the reports page when
 * the calendar preference is Jalali (the query still sends Gregorian ISO).
 */
export function JalaliRangePicker({
  value,
  onChange,
  maxDate,
}: {
  value: [Dayjs, Dayjs] | null;
  onChange: (v: [Dayjs, Dayjs] | null) => void;
  maxDate?: Dayjs;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const today = dayjsToJ(dayjs());
  const init = (): [JParts, JParts] =>
    value ? [dayjsToJ(value[0]), dayjsToJ(value[1])] : [today, today];
  const [s, setS] = useState<JParts>(init()[0]);
  const [e, setE] = useState<JParts>(init()[1]);

  const onOpenChange = (o: boolean) => {
    if (o) {
      const [a, b] = init();
      setS(a);
      setE(b);
    }
    setOpen(o);
  };

  const years = Array.from({ length: 8 }, (_, i) => today.y - i);
  const months = J_MONTHS.map((label, i) => ({ value: i + 1, label }));
  const daysOf = (p: JParts) =>
    Array.from({ length: jalaaliMonthLength(p.y, p.m) }, (_, i) => i + 1);

  const clampDay = (p: JParts): JParts => {
    const max = jalaaliMonthLength(p.y, p.m);
    return p.d > max ? { ...p, d: max } : p;
  };

  const apply = () => {
    let start = jToDayjs(clampDay(s));
    let end = jToDayjs(clampDay(e));
    if (end.isBefore(start)) [start, end] = [end, start];
    if (maxDate && end.isAfter(maxDate, "day")) end = maxDate;
    if (maxDate && start.isAfter(maxDate, "day")) start = maxDate;
    onChange([start.startOf("day"), end.startOf("day")]);
    setOpen(false);
  };

  const clear = () => {
    onChange(null);
    setOpen(false);
  };

  const editor = (
    p: JParts,
    set: (n: JParts) => void,
    label: string,
  ) => (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {label}
      </Text>
      <Space.Compact block style={{ marginTop: 4 }}>
        <Select
          style={{ width: 90 }}
          value={p.y}
          onChange={(y) => set(clampDay({ ...p, y }))}
          options={years.map((y) => ({ value: y, label: String(y) }))}
        />
        <Select
          style={{ width: 110 }}
          value={p.m}
          onChange={(m) => set(clampDay({ ...p, m }))}
          options={months}
        />
        <Select
          style={{ width: 72 }}
          value={p.d}
          onChange={(d) => set({ ...p, d })}
          options={daysOf(p).map((d) => ({ value: d, label: String(d) }))}
        />
      </Space.Compact>
    </div>
  );

  const content = (
    <div style={{ display: "grid", gap: 12, minWidth: 290 }}>
      {editor(s, setS, t("reports.from"))}
      {editor(e, setE, t("reports.to"))}
      <Space style={{ justifyContent: "flex-end" }}>
        {value && <Button size="small" onClick={clear}>{t("reports.clear")}</Button>}
        <Button size="small" type="primary" onClick={apply}>
          {t("reports.apply")}
        </Button>
      </Space>
    </div>
  );

  return (
    <Popover
      trigger="click"
      open={open}
      onOpenChange={onOpenChange}
      content={content}
      placement="bottomRight"
    >
      <Button icon={<CalendarOutlined />}>
        {value
          ? `${formatDay(value[0].toDate())} – ${formatDay(value[1].toDate())}`
          : t("reports.pickRange")}
      </Button>
    </Popover>
  );
}
