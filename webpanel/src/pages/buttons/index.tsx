import { useEffect, useState } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Spin,
  Switch,
  Tabs,
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
interface InlineItem {
  key: string;
  label: string;
  text: string;
  icon: string;
  style: string;
  default_style: string;
}

export function ButtonsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [labelItems, setLabelItems] = useState<BtnItem[]>([]);
  const [inlineItems, setInlineItems] = useState<InlineItem[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [icons, setIcons] = useState<Record<string, string>>({});
  const [styles, setStyles] = useState<Record<string, string>>({});
  const [premium, setPremium] = useState(false);

  const apply = (d: any) => {
    const li: BtnItem[] = d.items ?? [];
    const ii: InlineItem[] = d.inline ?? [];
    setLabelItems(li);
    setInlineItems(ii);
    setLabels(Object.fromEntries(li.map((i) => [i.key, i.value])));
    setTexts(Object.fromEntries(ii.map((i) => [i.key, i.text])));
    setIcons(Object.fromEntries(ii.map((i) => [i.key, i.icon])));
    setStyles(Object.fromEntries(ii.map((i) => [i.key, i.style])));
    setPremium(Boolean(d.premium_enabled));
  };

  useEffect(() => {
    api
      .get("/buttons")
      .then((r) => apply(r.data))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.patch("/buttons", {
        labels,
        premium_enabled: premium,
        icons,
        styles,
        texts,
      });
      apply(r.data);
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
  const styleOpts = [
    { value: "", label: t("buttons.style_none") },
    { value: "primary", label: t("buttons.style_primary") },
    { value: "success", label: t("buttons.style_success") },
    { value: "danger", label: t("buttons.style_danger") },
  ];

  const tabItems = [
    {
      key: "menu",
      label: t("buttons.tab_menu"),
      children: (
        <>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Text type="secondary">{t("buttons.hint")}</Text>
          </Card>
          <Row gutter={16}>
            {labelItems.map((it) => (
              <Col xs={24} sm={12} key={it.key}>
                <div style={{ marginBottom: 4 }}>
                  {label(it.key)}{" "}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    ({t("buttons.default")}: {it.default})
                  </Text>
                </div>
                <Input
                  allowClear
                  placeholder={it.default}
                  value={labels[it.key] ?? ""}
                  onChange={(e) =>
                    setLabels((s) => ({ ...s, [it.key]: e.target.value }))
                  }
                  style={{ marginBottom: 12 }}
                />
              </Col>
            ))}
          </Row>
        </>
      ),
    },
    {
      key: "inline",
      label: t("buttons.tab_inline"),
      children: (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message={t("buttons.premium_hint")}
          />
          <div
            style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}
          >
            <Switch checked={premium} onChange={setPremium} />
            <Text strong>{t("buttons.premium_enabled")}</Text>
          </div>
          <Row gutter={[16, 16]}>
            {inlineItems.map((it) => (
              <Col xs={24} lg={12} key={it.key}>
                <Card size="small" title={label(it.key)}>
                  <div style={{ marginBottom: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {t("buttons.text_label")} ({t("buttons.default")}: {it.label})
                    </Text>
                  </div>
                  <Input
                    allowClear
                    placeholder={it.label}
                    value={texts[it.key] ?? ""}
                    onChange={(e) =>
                      setTexts((s) => ({ ...s, [it.key]: e.target.value }))
                    }
                    style={{ marginBottom: 10 }}
                  />
                  <Row gutter={8}>
                    <Col xs={14}>
                      <Input
                        allowClear
                        placeholder={t("buttons.emoji_id_ph")}
                        value={icons[it.key] ?? ""}
                        onChange={(e) =>
                          setIcons((s) => ({ ...s, [it.key]: e.target.value }))
                        }
                        disabled={!premium}
                      />
                    </Col>
                    <Col xs={10}>
                      <Select
                        style={{ width: "100%" }}
                        options={styleOpts}
                        value={styles[it.key] ?? ""}
                        onChange={(v) =>
                          setStyles((s) => ({ ...s, [it.key]: v }))
                        }
                        disabled={!premium}
                        placeholder={it.default_style || t("buttons.style_none")}
                      />
                    </Col>
                  </Row>
                </Card>
              </Col>
            ))}
          </Row>
        </>
      ),
    },
  ];

  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>
        {t("buttons.title")}
      </Title>
      <Paragraph type="secondary">{t("buttons.subtitle")}</Paragraph>
      <Tabs defaultActiveKey="menu" items={tabItems} />
      <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
        {t("buttons.save")}
      </Button>
    </Card>
  );
}
