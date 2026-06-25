import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Row,
  Spin,
  Switch,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Title, Text } = Typography;

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
  "guardino_balance_warn",
  "guardino_balance_critical",
];

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
      const r = await api.patch("/settings", values);
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
      <div style={{ display: "grid", placeItems: "center", minHeight: 300 }}>
        <Spin />
      </div>
    );
  }

  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>
        {t("settings.title")}
      </Title>
      <Text type="secondary">{t("settings.subtitle")}</Text>

      <Form form={form} layout="vertical" onFinish={save} style={{ marginTop: 16 }}>
        <Divider orientation="left">{t("settings.behavior")}</Divider>
        <Row gutter={16}>
          {SWITCHES.map((k) => (
            <Col xs={24} sm={12} md={8} key={k}>
              <Form.Item name={k} label={t(`settings.${k}`)} valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          ))}
        </Row>

        <Divider orientation="left">{t("settings.values")}</Divider>
        <Row gutter={16}>
          <Col xs={24} sm={12} md={8}>
            <Form.Item
              name="default_username_prefix"
              label={t("settings.default_username_prefix")}
            >
              <Input />
            </Form.Item>
          </Col>
          {NUMBERS.map((k) => (
            <Col xs={24} sm={12} md={8} key={k}>
              <Form.Item name={k} label={t(`settings.${k}`)}>
                <InputNumber style={{ width: "100%" }} min={0} />
              </Form.Item>
            </Col>
          ))}
        </Row>

        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
          {t("settings.save")}
        </Button>
      </Form>
    </Card>
  );
}
