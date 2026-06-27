import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Collapse,
  Divider,
  Input,
  InputNumber,
  Row,
  Select,
  Skeleton,
  Switch,
  Tag,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Text } = Typography;
const CADENCE_TYPES = ["expiry", "low_data", "unused", "ended"];

const labelOf = (t: (k: string) => string, key: string) =>
  t(`automation.${key.replace("alert_", "al_")}`);

/**
 * Super-admin alert-config hub on the Automation page: edit the 4 alert texts,
 * the 2 alert glass-button colours + premium emoji, the inline-premium master
 * switch, and the per-type re-send cadence — all via /automation/alerts/config
 * (which merges button icon/style changes so other buttons aren't clobbered).
 */
export function AlertConfig() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [buttons, setButtons] = useState<any[]>([]);
  const [textsList, setTextsList] = useState<any[]>([]);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [icons, setIcons] = useState<Record<string, string>>({});
  const [styles, setStyles] = useState<Record<string, string>>({});
  const [premium, setPremium] = useState(false);
  const [cadence, setCadence] = useState<Record<string, number>>({});

  const apply = (d: any) => {
    setButtons(d.buttons ?? []);
    setTextsList(d.texts ?? []);
    setTexts(Object.fromEntries((d.texts ?? []).map((x: any) => [x.key, x.value])));
    setIcons(Object.fromEntries((d.buttons ?? []).map((x: any) => [x.key, x.icon])));
    setStyles(Object.fromEntries((d.buttons ?? []).map((x: any) => [x.key, x.style])));
    setPremium(!!d.premium_enabled);
    setCadence(d.cadence ?? {});
  };

  const load = async () => {
    if (loaded || loading) return;
    setLoading(true);
    try {
      const r = await api.get("/automation/alerts/config");
      apply(r.data);
      setLoaded(true);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.patch("/automation/alerts/config", {
        texts,
        icons,
        styles,
        premium_enabled: premium,
        cadence,
      });
      apply(r.data);
      message.success(t("automation.cfgSaved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const styleOpts = [
    { value: "", label: t("buttons.style_default") },
    { value: "none", label: t("buttons.style_raw") },
    { value: "primary", label: t("buttons.style_primary") },
    { value: "success", label: t("buttons.style_success") },
    { value: "danger", label: t("buttons.style_danger") },
  ];

  const body =
    loading && !loaded ? (
      <Skeleton active paragraph={{ rows: 6 }} />
    ) : (
      <>
        {/* texts */}
        <Text strong>{t("automation.cfgTexts")}</Text>
        <Row gutter={[16, 12]} style={{ marginTop: 8 }}>
          {textsList.map((x) => (
            <Col xs={24} lg={12} key={x.key}>
              <div style={{ marginBottom: 4, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                <Text>{labelOf(t, x.key)}</Text>
                {(x.variables ?? []).map((v: string) => (
                  <Tag key={v} style={{ margin: 0 }}>{`{${v}}`}</Tag>
                ))}
              </div>
              <Input.TextArea
                value={texts[x.key] ?? ""}
                onChange={(e) => setTexts((s) => ({ ...s, [x.key]: e.target.value }))}
                autoSize={{ minRows: 3, maxRows: 8 }}
                dir="auto"
                placeholder={t("automation.cfgTextPh")}
              />
            </Col>
          ))}
        </Row>

        <Divider />

        {/* buttons: premium switch + per-button icon + style */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <Switch checked={premium} onChange={setPremium} />
          <Text strong>{t("automation.cfgPremium")}</Text>
        </div>
        <Row gutter={[16, 12]}>
          {buttons.map((b) => (
            <Col xs={24} lg={12} key={b.key}>
              <Card size="small" title={b.label}>
                <Row gutter={8}>
                  <Col xs={14}>
                    <Input
                      placeholder={t("buttons.emoji_id_ph")}
                      value={icons[b.key] ?? ""}
                      onChange={(e) => setIcons((s) => ({ ...s, [b.key]: e.target.value }))}
                      disabled={!premium}
                      allowClear
                    />
                  </Col>
                  <Col xs={10}>
                    <Select
                      style={{ width: "100%" }}
                      options={styleOpts}
                      value={styles[b.key] ?? ""}
                      onChange={(v) => setStyles((s) => ({ ...s, [b.key]: v }))}
                    />
                  </Col>
                </Row>
              </Card>
            </Col>
          ))}
        </Row>

        <Divider />

        {/* cadence */}
        <Text strong>{t("automation.cfgCadence")}</Text>
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{t("automation.cfgCadenceHint")}</Text>
        </div>
        <Row gutter={[16, 12]} style={{ marginTop: 8 }}>
          {CADENCE_TYPES.map((ty) => (
            <Col xs={12} sm={8} md={6} key={ty}>
              <div style={{ marginBottom: 4 }}>
                <Text>{labelOf(t, `alert_${ty}`)}</Text>
              </div>
              <InputNumber
                min={0}
                style={{ width: "100%" }}
                value={cadence[ty] ?? 0}
                onChange={(v) => setCadence((s) => ({ ...s, [ty]: Number(v) || 0 }))}
                addonAfter={t("automation.hours")}
              />
            </Col>
          ))}
        </Row>

        <Button
          type="primary"
          icon={<SaveOutlined />}
          loading={saving}
          onClick={save}
          style={{ marginTop: 20 }}
        >
          {t("buttons.save")}
        </Button>
      </>
    );

  return (
    <Card style={{ marginTop: 16 }} styles={{ body: { padding: 0 } }}>
      <Collapse
        ghost
        onChange={(keys) => {
          if ((keys as string[]).length) load();
        }}
        items={[
          {
            key: "cfg",
            label: <Text strong>{t("automation.cfgTitle")}</Text>,
            children: body,
          },
        ]}
      />
    </Card>
  );
}
