import type { Key, ReactNode } from "react";
import { Card, Empty, Pagination, Skeleton, Table } from "antd";
import type { TablePaginationConfig, TableProps } from "antd";
import { useIsMobile } from "../hooks/useIsMobile";

/**
 * AntD Table that degrades to a stacked card list on phone screens (< md).
 * On mobile each row becomes a card built automatically from the same `columns`
 * (label = column title, value = column render/dataIndex), so pages don't need
 * to author a separate mobile layout — just swap <Table> → <ResponsiveTable>.
 * Columns with an empty title (action columns) render full-width in the footer.
 */
export function ResponsiveTable<T extends Record<string, any>>(
  props: TableProps<T>,
) {
  const mobile = useIsMobile();
  if (!mobile) return <Table<T> {...props} />;

  const { dataSource, columns, loading, rowKey, pagination } = props;
  const rows = (dataSource as T[]) ?? [];

  if (loading) {
    return (
      <div style={{ display: "grid", gap: 10 }}>
        {[0, 1, 2].map((i) => (
          <Card size="small" key={i}>
            <Skeleton active paragraph={{ rows: 3 }} title={false} />
          </Card>
        ))}
      </div>
    );
  }
  if (!rows.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: "32px 0" }} />;
  }

  const keyOf = (r: T, i: number): Key =>
    typeof rowKey === "function"
      ? (rowKey as (rec: T) => Key)(r)
      : rowKey
        ? (r[rowKey as string] as Key)
        : i;

  const cell = (col: any, r: T, i: number): ReactNode => {
    const raw = col.dataIndex != null ? r[col.dataIndex] : undefined;
    return col.render ? col.render(raw, r, i) : (raw as ReactNode);
  };

  const cols = (columns ?? []) as any[];

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {rows.map((r, i) => {
        const fields = cols.filter((c) => c.title);
        const actions = cols.filter((c) => !c.title);
        return (
          <Card size="small" key={keyOf(r, i)} styles={{ body: { padding: "10px 12px" } }}>
            {fields.map((c, ci) => (
              <div
                key={ci}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "3px 0",
                  fontSize: 13,
                }}
              >
                <span style={{ color: "var(--sc-chip-fg, #888)", flexShrink: 0 }}>
                  {c.title}
                </span>
                <span style={{ textAlign: "end", minWidth: 0, wordBreak: "break-word" }}>
                  {cell(c, r, i)}
                </span>
              </div>
            ))}
            {actions.length > 0 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 6,
                  marginTop: 8,
                  paddingTop: 8,
                  borderTop: "1px solid var(--sc-border, #eee)",
                }}
              >
                {actions.map((c, ci) => (
                  <span key={ci}>{cell(c, r, i)}</span>
                ))}
              </div>
            )}
          </Card>
        );
      })}
      {pagination && typeof pagination === "object" && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
          <Pagination
            size="small"
            {...(pagination as TablePaginationConfig)}
            showSizeChanger={false}
          />
        </div>
      )}
    </div>
  );
}
