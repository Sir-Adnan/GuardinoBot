import { useEffect, useState } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Divider,
  Input,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";

const { Text } = Typography;

interface BtnItem {
  key: string;
  default: string;
  value: string;
  icon: string;
  style: string;
  default_style: string;
}
interface InlineItem {
  key: string;
  label: string;
  text: string;
  icon: string;
  style: string;
  default_style: string;
}

interface FlatBtn {
  key: string;
  brk: boolean; // starts a new row
}

// Editable main-menu keys (admin_menu is intentionally excluded — it's super-user
// only and the bot always re-adds it). "test_services" is the dynamic placeholder.
const EDIT_KEYS = [
  "purchase",
  "proxies",
  "account",
  "charge",
  "referral",
  "help",
  "support",
  "test_services",
];

// Inline-button category grouping (derived from the key prefix) so the long list
// stays navigable in the editor.
const CAT_ORDER = [
  "proxy",
  "account",
  "purchase",
  "payment",
  "renew",
  "links",
  "reset",
  "reserve",
  "alerts",
  "common",
  "other",
];
const catOf = (key: string): string => {
  if (key.startsWith("pay_") || key === "purchase_pay") return "payment";
  if (key.startsWith("proxy_")) return "proxy";
  if (key.startsWith("account_")) return "account";
  if (key.startsWith("purchase_")) return "purchase";
  if (key.startsWith("renew_")) return "renew";
  if (key.startsWith("links_")) return "links";
  if (key.startsWith("reset_")) return "reset";
  if (key.startsWith("reserve_") || key === "show_reserve") return "reserve";
  if (key.startsWith("alert_")) return "alerts";
  if (key.startsWith("common_") || key === "confirm_action") return "common";
  return "other";
};

const flatFromRows = (rows: string[][]): FlatBtn[] => {
  const f: FlatBtn[] = [];
  (rows || []).forEach((row) => {
    (row || []).forEach((key, idx) => {
      if (key === "admin_menu" || !EDIT_KEYS.includes(key)) return;
      f.push({ key, brk: idx === 0 && f.length > 0 });
    });
  });
  if (f.length) f[0].brk = false;
  return f;
};

const rowsFromFlat = (flat: FlatBtn[]): string[][] => {
  const rows: string[][] = [];
  flat.forEach((it, i) => {
    if (i === 0 || it.brk) rows.push([it.key]);
    else rows[rows.length - 1].push(it.key);
  });
  return rows;
};

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
  const [replyPremium, setReplyPremium] = useState(false);
  const [flat, setFlat] = useState<FlatBtn[]>([]);
  const [search, setSearch] = useState("");

  const apply = (d: any) => {
    const li: BtnItem[] = d.items ?? [];
    const ii: InlineItem[] = d.inline ?? [];
    setLabelItems(li);
    setInlineItems(ii);
    setLabels(Object.fromEntries(li.map((i) => [i.key, i.value])));
    setTexts(Object.fromEntries(ii.map((i) => [i.key, i.text])));
    // icons/styles are shared by inline buttons AND main-menu (reply) buttons.
    const all: { key: string; icon?: string; style?: string }[] = [...ii, ...li];
    setIcons(Object.fromEntries(all.map((i) => [i.key, i.icon ?? ""])));
    setStyles(Object.fromEntries(all.map((i) => [i.key, i.style ?? ""])));
    setPremium(Boolean(d.premium_enabled));
    setReplyPremium(Boolean(d.reply_premium_enabled));
    setFlat(flatFromRows(d.main_layout ?? []));
  };

  const moveFlat = (i: number, dir: -1 | 1) =>
    setFlat((f) => {
      const j = i + dir;
      if (j < 0 || j >= f.length) return f;
      const c = [...f];
      [c[i], c[j]] = [c[j], c[i]];
      if (c.length) c[0].brk = false;
      return c;
    });
  const toggleBrk = (i: number) =>
    setFlat((f) => f.map((it, idx) => (idx === i ? { ...it, brk: !it.brk } : it)));
  const disableBtn = (i: number) =>
    setFlat((f) => {
      const c = f.filter((_, idx) => idx !== i);
      if (c.length) c[0].brk = false;
      return c;
    });
  const enableBtn = (key: string) =>
    setFlat((f) => [...f, { key, brk: true }]);

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
        reply_premium_enabled: replyPremium,
        icons,
        styles,
        texts,
        main_layout: rowsFromFlat(flat),
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
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
        <Skeleton active paragraph={{ rows: 6 }} style={{ marginTop: 24 }} />
      </Card>
    );
  }

  const label = (key: string) => {
    const k = `buttons.k.${key}`;
    const tr = t(k);
    return tr === k ? key : tr;
  };
  const styleOpts = [
    { value: "", label: t("buttons.style_default") },
    { value: "none", label: t("buttons.style_raw") },
    { value: "primary", label: t("buttons.style_primary") },
    { value: "success", label: t("buttons.style_success") },
    { value: "danger", label: t("buttons.style_danger") },
  ];

  const renderInlineCard = (it: InlineItem) => (
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
          onChange={(e) => setTexts((s) => ({ ...s, [it.key]: e.target.value }))}
          style={{ marginBottom: 10 }}
        />
        <Row gutter={8}>
          <Col xs={14}>
            <Input
              allowClear
              placeholder={t("buttons.emoji_id_ph")}
              value={icons[it.key] ?? ""}
              onChange={(e) => setIcons((s) => ({ ...s, [it.key]: e.target.value }))}
              disabled={!premium}
            />
          </Col>
          <Col xs={10}>
            <Select
              style={{ width: "100%" }}
              options={styleOpts}
              value={styles[it.key] ?? ""}
              onChange={(v) => setStyles((s) => ({ ...s, [it.key]: v }))}
              disabled={!premium}
              placeholder={it.default_style || t("buttons.style_none")}
            />
          </Col>
        </Row>
      </Card>
    </Col>
  );

  const tabItems = [
    {
      key: "menu",
      label: t("buttons.tab_menu"),
      children: (
        <>
          <Card
            size="small"
            title={t("buttons.layout_title")}
            style={{ marginBottom: 16 }}
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={t("buttons.layout_hint")}
            />
            {flat.map((it, i) => (
              <div key={`${it.key}-${i}`}>
                {it.brk && i > 0 && (
                  <Divider plain style={{ margin: "8px 0", fontSize: 12 }}>
                    {t("buttons.new_row")}
                  </Divider>
                )}
                <Space
                  style={{
                    width: "100%",
                    justifyContent: "space-between",
                    padding: "4px 0",
                  }}
                >
                  <Text>{label(it.key)}</Text>
                  <Space size={4}>
                    <Tooltip title={t("buttons.new_row")}>
                      <Switch
                        size="small"
                        checkedChildren="↵"
                        checked={it.brk}
                        disabled={i === 0}
                        onChange={() => toggleBrk(i)}
                      />
                    </Tooltip>
                    <Button
                      size="small"
                      icon={<ArrowUpOutlined />}
                      disabled={i === 0}
                      onClick={() => moveFlat(i, -1)}
                    />
                    <Button
                      size="small"
                      icon={<ArrowDownOutlined />}
                      disabled={i === flat.length - 1}
                      onClick={() => moveFlat(i, 1)}
                    />
                    <Button
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => disableBtn(i)}
                    />
                  </Space>
                </Space>
              </div>
            ))}
            {EDIT_KEYS.filter((k) => !flat.some((f) => f.key === k)).length >
              0 && (
              <>
                <Divider plain style={{ margin: "12px 0", fontSize: 12 }}>
                  {t("buttons.disabled")}
                </Divider>
                <Space wrap>
                  {EDIT_KEYS.filter((k) => !flat.some((f) => f.key === k)).map(
                    (k) => (
                      <Tag
                        key={k}
                        icon={<PlusOutlined />}
                        style={{ cursor: "pointer", padding: "4px 8px" }}
                        onClick={() => enableBtn(k)}
                      >
                        {label(k)}
                      </Tag>
                    ),
                  )}
                </Space>
              </>
            )}
          </Card>
          <Card size="small" title={t("buttons.labels_title")}>
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message={t("buttons.reply_premium_hint")}
            />
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 16,
              }}
            >
              <Switch checked={replyPremium} onChange={setReplyPremium} />
              <Text strong>{t("buttons.reply_premium_enabled")}</Text>
            </div>
            <Row gutter={[16, 8]}>
              {labelItems.map((it) => (
                <Col xs={24} lg={12} key={it.key}>
                  <Card size="small" title={label(it.key)} style={{ marginBottom: 4 }}>
                    <div style={{ marginBottom: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {t("buttons.text_label")} ({t("buttons.default")}: {it.default})
                      </Text>
                    </div>
                    <Input
                      allowClear
                      placeholder={it.default}
                      value={labels[it.key] ?? ""}
                      onChange={(e) =>
                        setLabels((s) => ({ ...s, [it.key]: e.target.value }))
                      }
                      style={{ marginBottom: 10 }}
                    />
                    {it.key !== "admin_menu" && (
                      <Row gutter={8}>
                        <Col xs={14}>
                          <Input
                            allowClear
                            placeholder={t("buttons.emoji_id_ph")}
                            value={icons[it.key] ?? ""}
                            onChange={(e) =>
                              setIcons((s) => ({ ...s, [it.key]: e.target.value }))
                            }
                            disabled={!replyPremium}
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
                            disabled={!replyPremium}
                          />
                        </Col>
                      </Row>
                    )}
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
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
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 16,
              flexWrap: "wrap",
            }}
          >
            <Switch checked={premium} onChange={setPremium} />
            <Text strong>{t("buttons.premium_enabled")}</Text>
            <Input.Search
              allowClear
              placeholder={t("buttons.search_ph")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ marginInlineStart: "auto", maxWidth: 260 }}
            />
          </div>
          {(() => {
            const q = search.trim().toLowerCase();
            const filtered = inlineItems.filter(
              (it) =>
                !q ||
                it.key.toLowerCase().includes(q) ||
                String(it.label || "").toLowerCase().includes(q) ||
                label(it.key).toLowerCase().includes(q),
            );
            if (!filtered.length)
              return <Text type="secondary">{t("buttons.noMatch")}</Text>;
            const cats = CAT_ORDER.filter((c) =>
              filtered.some((it) => catOf(it.key) === c),
            );
            return cats.map((c) => (
              <div key={c} style={{ marginBottom: 18 }}>
                <Text strong style={{ display: "block", marginBottom: 10, fontSize: 13 }}>
                  {t(`buttons.cat_${c}`, c)}
                </Text>
                <Row gutter={[16, 16]}>
                  {filtered.filter((it) => catOf(it.key) === c).map(renderInlineCard)}
                </Row>
              </div>
            ));
          })()}
        </>
      ),
    },
  ];

  return (
    <Card>
      <PageHeader title={t("buttons.title")} subtitle={t("buttons.subtitle")} />
      <Tabs defaultActiveKey="menu" items={tabItems} />
      <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
        {t("buttons.save")}
      </Button>
    </Card>
  );
}
