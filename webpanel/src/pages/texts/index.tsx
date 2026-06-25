import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Input,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Title, Text, Paragraph } = Typography;

interface TextItem {
  key: string;
  value: string;
  variables: string[];
}

export function TextsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [items, setItems] = useState<TextItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    api
      .get("/texts")
      .then((r) => {
        const list: TextItem[] = r.data.items ?? [];
        setItems(list);
        setDrafts(Object.fromEntries(list.map((i) => [i.key, i.value])));
      })
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (key: string) => {
    setSavingKey(key);
    try {
      const r = await api.patch("/texts", { key, value: drafts[key] ?? "" });
      setItems((arr) =>
        arr.map((i) => (i.key === key ? { ...i, value: r.data.value } : i)),
      );
      setDrafts((d) => ({ ...d, [key]: r.data.value }));
      message.success(t("texts.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSavingKey(null);
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
    const k = `texts.k.${key}`;
    const tr = t(k);
    return tr === k ? key : tr;
  };

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>
        {t("texts.title")}
      </Title>
      <Paragraph type="secondary">{t("texts.subtitle")}</Paragraph>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Text type="secondary">{t("texts.emoji_hint")}</Text>
      </Card>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {items.map((it) => {
          const dirty = (drafts[it.key] ?? "") !== it.value;
          return (
            <Card
              key={it.key}
              title={label(it.key)}
              size="small"
              extra={
                <Button
                  type="primary"
                  size="small"
                  icon={<SaveOutlined />}
                  loading={savingKey === it.key}
                  disabled={!dirty}
                  onClick={() => save(it.key)}
                >
                  {t("texts.save")}
                </Button>
              }
            >
              {it.variables.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ marginInlineEnd: 6 }}>
                    {t("texts.variables")}:
                  </Text>
                  {it.variables.map((v) => (
                    <Tag key={v} className="mono">{`{${v}}`}</Tag>
                  ))}
                </div>
              )}
              <Input.TextArea
                value={drafts[it.key] ?? ""}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [it.key]: e.target.value }))
                }
                autoSize={{ minRows: 3, maxRows: 14 }}
                dir="auto"
              />
            </Card>
          );
        })}
      </Space>
    </div>
  );
}
