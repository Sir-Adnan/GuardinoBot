import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Empty,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Skeleton,
  Tag,
  Typography,
  theme,
} from "antd";
import {
  BellOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EyeOutlined,
  SendOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useCustom, useGetIdentity } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_SUPER, fmtDate, fmtNum } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";
import { AlertConfig } from "./AlertConfig";

const { Text } = Typography;

const NUM_STYLE = { fontVariantNumeric: "tabular-nums" } as const;

const STATUS_COLORS: Record<string, string> = {
  running: "processing",
  done: "success",
  canceled: "default",
  crashed: "error",
  idle: "default",
};

const ALERT_STATUS_COLORS: Record<string, string> = {
  running: "processing",
  done: "success",
  deferred: "gold",
  disabled: "default",
  idle: "default",
};

export function AutomationPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { message } = AntdApp.useApp();
  const { data: me } = useGetIdentity<any>();
  const isSuper = (me?.role ?? 0) >= ROLE_SUPER;
  const { data, isLoading, refetch } = useCustom<any>({
    url: "/automation/broadcast",
    method: "get",
    queryOptions: { refetchInterval: 4000 },
  });
  const d = data?.data;
  const st = d?.status ?? "idle";
  const running = st === "running";

  const { data: alertsData, refetch: refetchAlerts } = useCustom<any>({
    url: "/automation/alerts",
    method: "get",
    queryOptions: { refetchInterval: 5000 },
  });
  const a = alertsData?.data;
  const alertState = a?.state ?? "idle";
  const alertRunning = alertState === "running";

  const cancel = async () => {
    try {
      await api.post("/automation/broadcast/cancel");
      message.success(t("automation.canceling"));
      refetch();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const runAlerts = async () => {
    try {
      await api.post("/automation/alerts/run");
      message.success(t("automation.alertsQueued"));
      setTimeout(refetchAlerts, 1000);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewItems, setPreviewItems] = useState<any[] | null>(null);

  const openPreview = async () => {
    setPreviewOpen(true);
    setPreviewItems(null);
    try {
      const r = await api.get("/automation/alerts/preview");
      setPreviewItems(r.data.items ?? []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
      setPreviewItems([]);
    }
  };

  return (
    <div>
      <PageHeader title={t("automation.title")} subtitle={t("automation.subtitle")} />

      <Card
        title={t("automation.broadcast")}
        extra={
          running ? (
            <Popconfirm
              title={t("automation.cancelConfirm")}
              okButtonProps={{ danger: true }}
              onConfirm={cancel}
            >
              <Button danger icon={<StopOutlined />}>
                {t("automation.cancel")}
              </Button>
            </Popconfirm>
          ) : null
        }
      >
        {isLoading && !d ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <>
            <div style={{ marginBottom: 16 }}>
              <Text>{t("automation.status")}: </Text>
              <Tag color={STATUS_COLORS[st] || "default"}>{t(`automation.s_${st}`)}</Tag>
              {d?.kind ? <Tag>{d.kind}</Tag> : null}
            </div>

            {d?.total > 0 || running ? (
              <Progress
                percent={d?.progress ?? 0}
                status={running ? "active" : st === "done" ? "success" : "normal"}
              />
            ) : null}

            <Row gutter={[12, 12]} style={{ marginTop: 16 }}>
              <Col xs={24} sm={8}>
                <StatCard
                  label={t("automation.success")}
                  value={<span style={{ color: token.colorSuccess }}>{fmtNum(d?.success)}</span>}
                  icon={<CheckCircleOutlined />}
                />
              </Col>
              <Col xs={24} sm={8}>
                <StatCard
                  label={t("automation.fails")}
                  value={<span style={{ color: token.colorError }}>{fmtNum(d?.fails)}</span>}
                  icon={<CloseCircleOutlined />}
                />
              </Col>
              <Col xs={24} sm={8}>
                <StatCard label={t("automation.total")} value={fmtNum(d?.total)} icon={<SendOutlined />} />
              </Col>
            </Row>

            {st === "idle" ? (
              <Text type="secondary">{t("automation.idleHint")}</Text>
            ) : null}
          </>
        )}
      </Card>

      <Card
        title={
          <span>
            <BellOutlined style={{ marginInlineEnd: 8 }} />
            {t("automation.alerts")}
          </span>
        }
        style={{ marginTop: 16 }}
        extra={
          <span style={{ display: "inline-flex", gap: 8 }}>
            <Button icon={<EyeOutlined />} onClick={openPreview}>
              {t("automation.preview")}
            </Button>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={alertRunning}
              onClick={runAlerts}
            >
              {t("automation.runNow")}
            </Button>
          </span>
        }
      >
        <Text type="secondary">{t("automation.alertsHint")}</Text>
        <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Text>{t("automation.status")}: </Text>
          <Tag color={ALERT_STATUS_COLORS[alertState] || "default"}>
            {t(`automation.as_${alertState}`)}
          </Tag>
          {a?.last_run ? (
            <Text type="secondary">
              {t("automation.lastRun")}: {fmtDate(a.last_run)}
            </Text>
          ) : null}
          {a?.last_run ? (
            <Text type="secondary">
              · {t("automation.sentCount")}: <span style={NUM_STYLE}>{fmtNum(a?.sent)}</span>
            </Text>
          ) : null}
        </div>
      </Card>

      {isSuper && <AlertConfig />}

      <Modal
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        title={t("automation.previewTitle")}
        footer={null}
        width={560}
      >
        {previewItems === null ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : previewItems.length === 0 ? (
          <Empty />
        ) : (
          <div style={{ display: "grid", gap: 14 }}>
            {previewItems.map((it) => (
              <div key={it.type}>
                <div style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
                  <Text strong>{t(`automation.${it.type.replace("alert_", "al_")}`)}</Text>
                  {it.is_default ? (
                    <Tag color="default">{t("automation.usingDefault")}</Tag>
                  ) : null}
                </div>
                <div
                  style={{
                    background: token.colorPrimaryBg,
                    border: `1px solid ${token.colorPrimaryBorder}`,
                    borderRadius: "14px 14px 4px 14px",
                    padding: "10px 14px",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    lineHeight: 1.7,
                    fontSize: 14,
                  }}
                  dangerouslySetInnerHTML={{ __html: it.text || "—" }}
                />
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
