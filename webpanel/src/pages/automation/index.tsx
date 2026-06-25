import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Popconfirm,
  Progress,
  Row,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { StopOutlined } from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtNum } from "../../utils/format";

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  running: "processing",
  done: "success",
  canceled: "default",
  crashed: "error",
  idle: "default",
};

export function AutomationPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { data, isLoading, refetch } = useCustom<any>({
    url: "/automation/broadcast",
    method: "get",
    queryOptions: { refetchInterval: 4000 },
  });
  const d = data?.data;
  const st = d?.status ?? "idle";
  const running = st === "running";

  const cancel = async () => {
    try {
      await api.post("/automation/broadcast/cancel");
      message.success(t("automation.canceling"));
      refetch();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <Title level={4} style={{ margin: 0 }}>
          {t("automation.title")}
        </Title>
        <Text type="secondary">{t("automation.subtitle")}</Text>
      </div>

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
          <div style={{ display: "grid", placeItems: "center", minHeight: 120 }}>
            <Spin />
          </div>
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

            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
              <Col xs={8}>
                <Statistic
                  title={t("automation.success")}
                  value={fmtNum(d?.success)}
                  valueStyle={{ fontFamily: "'IBM Plex Mono', monospace", color: "#10b981" }}
                />
              </Col>
              <Col xs={8}>
                <Statistic
                  title={t("automation.fails")}
                  value={fmtNum(d?.fails)}
                  valueStyle={{ fontFamily: "'IBM Plex Mono', monospace", color: "#ef4444" }}
                />
              </Col>
              <Col xs={8}>
                <Statistic
                  title={t("automation.total")}
                  value={fmtNum(d?.total)}
                  valueStyle={{ fontFamily: "'IBM Plex Mono', monospace" }}
                />
              </Col>
            </Row>

            {st === "idle" ? (
              <Text type="secondary">{t("automation.idleHint")}</Text>
            ) : null}
          </>
        )}
      </Card>
    </div>
  );
}
