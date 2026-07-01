import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Skeleton,
  Switch,
  Tabs,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";
import { ForceJoinEditor } from "./ForceJoin";
import { ReportsGroupEditor } from "./ReportsGroup";

const SWITCHES = [
  "access_only",
  "referral_system",
  "reset_password_button",
  "show_connect_links_button",
  "show_test_service_in_menu",
  "phone_number_verify",
];
const NUMBERS = [
  "remind_invoices_each_n_days",
  "remind_invoices_after_amount",
  "default_daily_test_services",
  "delete_expired_users_after_days",
  "referral_discount_percent",
  "cancel_payback_fee",
  "cancel_payback_days",
  "on_hold_timeout_seconds",
  "guardino_balance_warn",
  "guardino_balance_critical",
];
const TAG_LISTS = ["charge_amount_list", "charge_amount_orders"];
const ALERT_SWITCHES = [
  "alerts_enabled",
  "notify_expiry_enabled",
  "notify_low_data_enabled",
  "notify_unused_enabled",
  "notify_ended_enabled",
  "alerts_quiet_enabled",
];
const ALERT_NUMBERS = [
  "notify_expiry_days",
  "notify_traffic_percent",
  "notify_data_remaining_gb",
  "notify_unused_days",
  "alerts_quiet_start_hour",
  "alerts_quiet_end_hour",
];

const toNumbers = (arr: any): number[] =>
  Array.isArray(arr)
    ? arr.map((x) => Number(x)).filter((n) => Number.isFinite(n))
    : [];

export function SettingsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get("/settings")
      .then((r) => form.setFieldsValue(r.data))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (values: any) => {
    setSaving(true);
    try {
      const payload = {
        ...values,
        charge_amount_list: toNumbers(values.charge_amount_list),
        charge_amount_orders: toNumbers(values.charge_amount_orders),
        notify_expiry_steps_hours: toNumbers(values.notify_expiry_steps_hours),
      };
      const r = await api.patch("/settings", payload);
      form.setFieldsValue(r.data);
      message.success(t("settings.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
        <Skeleton active paragraph={{ rows: 6 }} style={{ marginTop: 24 }} />
      </Card>
    );
  }

  const switchItem = (k: string) => (
    <Col xs={24} sm={12} md={8} key={k}>
      <Form.Item name={k} label={t(`settings.${k}`)} valuePropName="checked">
        <Switch />
      </Form.Item>
    </Col>
  );
  const numberItem = (k: string) => (
    <Col xs={24} sm={12} md={8} key={k}>
      <Form.Item name={k} label={t(`settings.${k}`)}>
        <InputNumber style={{ width: "100%" }} min={0} />
      </Form.Item>
    </Col>
  );

  const tabItems = [
    {
      key: "general",
      label: t("settings.behavior"),
      forceRender: true,
      children: <Row gutter={16}>{SWITCHES.map(switchItem)}</Row>,
    },
    {
      key: "values",
      label: t("settings.values"),
      forceRender: true,
      children: (
        <Row gutter={16}>
          <Col xs={24} sm={12} md={8}>
            <Form.Item
              name="default_username_prefix"
              label={t("settings.default_username_prefix")}
            >
              <Input />
            </Form.Item>
          </Col>
          {NUMBERS.map(numberItem)}
        </Row>
      ),
    },
    {
      key: "advanced",
      label: t("settings.advanced"),
      forceRender: true,
      children: (
        <Row gutter={16}>
          <Col xs={24} sm={12} md={8}>
            <Form.Item
              name="username_generator"
              label={t("settings.username_generator")}
            >
              <Select
                options={[
                  { value: "randomized", label: t("settings.ug_randomized") },
                  { value: "incremental", label: t("settings.ug_incremental") },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Form.Item
              name="transaction_logs"
              label={t("settings.transaction_logs")}
              tooltip={t("settings.logs_hint")}
            >
              <Input allowClear />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Form.Item
              name="orders_logs"
              label={t("settings.orders_logs")}
              tooltip={t("settings.logs_hint")}
            >
              <Input allowClear />
            </Form.Item>
          </Col>
          {TAG_LISTS.map((k) => (
            <Col xs={24} sm={12} key={k}>
              <Form.Item
                name={k}
                label={t(`settings.${k}`)}
                tooltip={t("settings.charge_hint")}
              >
                <Select
                  mode="tags"
                  tokenSeparators={[",", " "]}
                  open={false}
                  suffixIcon={null}
                  placeholder="10000, 50000, 100000"
                />
              </Form.Item>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: "alerts",
      label: t("settings.alerts"),
      forceRender: true,
      children: (
        <Row gutter={16}>
          {ALERT_SWITCHES.map(switchItem)}
          {ALERT_NUMBERS.map(numberItem)}
          <Col xs={24} sm={12}>
            <Form.Item
              name="notify_expiry_steps_hours"
              label={t("settings.notify_expiry_steps_hours")}
              tooltip={t("settings.expiry_steps_hint")}
            >
              <Select
                mode="tags"
                tokenSeparators={[",", " "]}
                suffixIcon={null}
                placeholder="72, 24, 12"
              />
            </Form.Item>
          </Col>
        </Row>
      ),
    },
  ];

  return (
    <>
      <Card>
        <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

        <Form form={form} layout="vertical" onFinish={save} style={{ marginTop: 16 }}>
          <Tabs defaultActiveKey="general" items={tabItems} />
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
            {t("settings.save")}
          </Button>
        </Form>
      </Card>

      <Card style={{ marginTop: 16 }} title={t("reportsGroup.title")}>
        <ReportsGroupEditor />
      </Card>

      <Card style={{ marginTop: 16 }} title={t("forceJoin.title")}>
        <ForceJoinEditor />
      </Card>
    </>
  );
}
