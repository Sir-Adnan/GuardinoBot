import { Button, Card, Empty, Skeleton, Tag, Tooltip, Typography } from "antd";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  ReloadOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtDate, fmtToman } from "../../utils/format";

const { Text } = Typography;

const PANEL_COLORS: Record<string, string> = {
  marzban: "blue",
  pasarguard: "geekblue",
  guardino: "green",
};
const BAL_COLORS: Record<string, string> = {
  ok: "green",
  warn: "gold",
  critical: "red",
};

/**
 * Live panel reachability + Guardino reseller balance. Lazy & self-contained
 * (one network call per panel) so it never slows the main dashboard summary;
 * has its own loading skeleton and a manual refresh.
 */
export function PanelHealth() {
  const { t } = useTranslation();
  const { data, isFetching, refetch } = useCustom<any>({
    url: "/dashboard/panel-health",
    method: "get",
  });
  const d = data?.data;
  const items: any[] = d?.items ?? [];

  return (
    <Card
      className="gb-lift"
      style={{ borderRadius: 16, marginTop: 16 }}
      title={t("dashboard.panelHealth")}
      extra={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
          {d?.checked_at ? (
            <Text type="secondary" style={{ fontSize: 11.5 }}>
              {fmtDate(d.checked_at)}
            </Text>
          ) : null}
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={isFetching}
            onClick={() => refetch()}
          >
            {t("dashboard.refresh")}
          </Button>
        </span>
      }
    >
      {isFetching && !d ? (
        <Skeleton active paragraph={{ rows: 3 }} />
      ) : items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {items.map((it) => (
            <div
              key={it.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                flexWrap: "wrap",
                padding: "8px 4px",
                borderBottom: "1px solid var(--sc-border, rgba(0,0,0,0.06))",
              }}
            >
              {it.ok ? (
                <CheckCircleFilled style={{ color: "#10b981" }} />
              ) : (
                <CloseCircleFilled style={{ color: "#ef4444" }} />
              )}
              <Text strong style={{ minWidth: 0 }}>{it.name}</Text>
              <Tag color={PANEL_COLORS[it.panel_type] || "default"}>{it.panel_type}</Tag>
              <span style={{ marginInlineStart: "auto", display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                {it.ok ? (
                  <>
                    {it.admin ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>{it.admin}</Text>
                    ) : null}
                    {it.balance != null ? (
                      <Tooltip title={t("dashboard.ph_balance")}>
                        <Tag color={BAL_COLORS[it.balance_level] || "default"} style={{ fontVariantNumeric: "tabular-nums" }}>
                          {fmtToman(it.balance)}
                        </Tag>
                      </Tooltip>
                    ) : null}
                    <Tag color="success">{t("dashboard.ph_ok")}</Tag>
                  </>
                ) : (
                  <Tag color="error">{t(`dashboard.ph_${it.error || "error"}`)}</Tag>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
