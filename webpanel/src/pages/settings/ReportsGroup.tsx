import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Alert,
  Button,
  Col,
  Divider,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import {
  ApiOutlined,
  CloudDownloadOutlined,
  DisconnectOutlined,
  MoonOutlined,
  SaveOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Text } = Typography;

interface TopicRow {
  key: string;
  title: string;
  thread_id: number | null;
  enabled: boolean;
}

interface ReportsGroupData {
  connected: boolean;
  group_id: number | null;
  topics: TopicRow[];
  backup_interval_hours: number;
  nightly_report_enabled: boolean;
}

/**
 * Topics-group reporting settings (super-admin). Reads/writes
 * GET/PATCH /settings/reports-group; test actions go through
 * POST /settings/reports-group/test → a Redis queue the bot drains within ~15s
 * (the reports pipeline lives in the bot process, not the API).
 */
export function ReportsGroupEditor() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [data, setData] = useState<ReportsGroupData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testTopic, setTestTopic] = useState<string | undefined>();
  const [testing, setTesting] = useState<string | null>(null);

  const load = () =>
    api
      .get("/settings/reports-group")
      .then((r) => setData(r.data))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const patch = async (body: any, successMsg?: string) => {
    setSaving(true);
    try {
      const r = await api.patch("/settings/reports-group", body);
      setData(r.data);
      message.success(successMsg ?? t("reportsGroup.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const save = () => {
    if (!data) return;
    return patch({
      disabled_topics: data.topics.filter((x) => !x.enabled).map((x) => x.key),
      backup_interval_hours: data.backup_interval_hours,
      nightly_report_enabled: data.nightly_report_enabled,
    });
  };

  const runTest = async (body: any, key: string) => {
    setTesting(key);
    try {
      await api.post("/settings/reports-group/test", body);
      message.success(t("reportsGroup.queued"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setTesting(null);
    }
  };

  if (loading || !data) return <Skeleton active paragraph={{ rows: 4 }} />;

  return (
    <div>
      <Space wrap style={{ marginBottom: 12 }}>
        {data.connected ? (
          <Tag color="green" icon={<ApiOutlined />}>
            {t("reportsGroup.connected")}
          </Tag>
        ) : (
          <Tag color="red" icon={<DisconnectOutlined />}>
            {t("reportsGroup.not_connected")}
          </Tag>
        )}
        {data.group_id && (
          <Text type="secondary">
            {t("reportsGroup.group_id")}: <Text code>{data.group_id}</Text>
          </Text>
        )}
      </Space>

      {!data.connected && (
        <Alert type="info" showIcon message={t("reportsGroup.connect_hint")} />
      )}

      {data.connected && (
        <>
          <Divider orientation="right" plain>
            {t("reportsGroup.topics")}
          </Divider>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={t("reportsGroup.topic_enabled_hint")}
          />
          <Row gutter={[16, 8]}>
            {data.topics.map((topic) => (
              <Col xs={24} sm={12} md={8} key={topic.key}>
                <Space>
                  <Switch
                    checked={topic.enabled}
                    onChange={(v) =>
                      setData({
                        ...data,
                        topics: data.topics.map((x) =>
                          x.key === topic.key ? { ...x, enabled: v } : x
                        ),
                      })
                    }
                  />
                  <Text>{topic.title}</Text>
                </Space>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 8]} style={{ marginTop: 16 }}>
            <Col xs={24} sm={12}>
              <Space>
                <Switch
                  checked={data.nightly_report_enabled}
                  onChange={(v) => setData({ ...data, nightly_report_enabled: v })}
                />
                <Text>
                  <MoonOutlined /> {t("reportsGroup.nightly")}
                </Text>
              </Space>
            </Col>
            <Col xs={24} sm={12}>
              <Space>
                <InputNumber
                  min={0}
                  max={24}
                  value={data.backup_interval_hours}
                  onChange={(v) =>
                    setData({ ...data, backup_interval_hours: Number(v ?? 0) })
                  }
                />
                <Text>{t("reportsGroup.backup_interval")}</Text>
              </Space>
            </Col>
          </Row>

          <Space style={{ marginTop: 16 }} wrap>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={save}
            >
              {t("settings.save")}
            </Button>
            <Popconfirm
              title={t("reportsGroup.disconnect_confirm")}
              onConfirm={() => patch({ disconnect: true })}
            >
              <Button danger icon={<DisconnectOutlined />}>
                {t("reportsGroup.disconnect")}
              </Button>
            </Popconfirm>
          </Space>

          <Divider orientation="right" plain>
            {t("reportsGroup.test")}
          </Divider>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={t("reportsGroup.test_hint")}
          />
          <Space wrap>
            <Space.Compact>
              <Select
                style={{ minWidth: 220 }}
                placeholder={t("reportsGroup.test_topic_ph")}
                value={testTopic}
                onChange={setTestTopic}
                options={data.topics.map((x) => ({ value: x.key, label: x.title }))}
              />
              <Button
                icon={<SendOutlined />}
                disabled={!testTopic}
                loading={testing === "topic"}
                onClick={() => runTest({ action: "topic", topic: testTopic }, "topic")}
              >
                {t("reportsGroup.test_topic")}
              </Button>
            </Space.Compact>
            <Button
              icon={<MoonOutlined />}
              loading={testing === "nightly"}
              onClick={() => runTest({ action: "nightly" }, "nightly")}
            >
              {t("reportsGroup.run_nightly")}
            </Button>
            <Button
              icon={<CloudDownloadOutlined />}
              loading={testing === "backup"}
              onClick={() => runTest({ action: "backup" }, "backup")}
            >
              {t("reportsGroup.run_backup")}
            </Button>
          </Space>
        </>
      )}
    </div>
  );
}
