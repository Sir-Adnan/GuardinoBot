import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  Row,
  Spin,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Title, Text, Paragraph } = Typography;

interface BtnItem {
  key: string;
  default: string;
  value: string;
}

export function ButtonsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm();
  const [items, setItems] = useState<BtnItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const apply = (list: BtnItem[]) => {
    setItems(list);
    form.setFieldsValue(Object.fromEntries(list.map((i) => [i.key, i.value])));
  };

  useEffect(() => {
    api
      .get("/buttons")
      .then((r) => apply(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (values: any) => {
    setSaving(true);
    try {
      const r = await api.patch("/buttons", { labels: values });
      apply(r.data.items ?? []);
      message.success(t("buttons.saved"));
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

  const label = (key: string) => {
    const k = `buttons.k.${key}`;
    const tr = t(k);
    return tr === k ? key : tr;
  };

  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>
        {t("buttons.title")}
      </Title>
      <Paragraph type="secondary">{t("buttons.subtitle")}</Paragraph>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Text type="secondary">{t("buttons.hint")}</Text>
      </Card>

      <Form form={form} layout="vertical" onFinish={save}>
        <Row gutter={16}>
          {items.map((it) => (
            <Col xs={24} sm={12} key={it.key}>
              <Form.Item
                name={it.key}
                label={label(it.key)}
                extra={`${t("buttons.default")}: ${it.default}`}
              >
                <Input allowClear placeholder={it.default} />
              </Form.Item>
            </Col>
          ))}
        </Row>
        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
          {t("buttons.save")}
        </Button>
      </Form>
    </Card>
  );
}
