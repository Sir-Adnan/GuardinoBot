import { useContext, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  Alert,
  App as AntdApp,
  Badge,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
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
  theme as antdTheme,
} from "antd";
import {
  AppstoreOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";
import { ColorModeContext } from "../../contexts/color-mode";

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
  "admin",
  "common",
  "other",
];
const catOf = (key: string): string => {
  if (key.startsWith("admin_")) return "admin";
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

// Telegram-ish colours for the live pill preview of each style value.
const STYLE_FILL: Record<string, { bg: string; fg: string; border?: string }> = {
  primary: { bg: "#2f6fed", fg: "#fff" },
  success: { bg: "#10b981", fg: "#fff" },
  danger: { bg: "#ef4444", fg: "#fff" },
};

export function ButtonsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { token } = antdTheme.useToken();
  const { mode } = useContext(ColorModeContext);
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
  const [origSig, setOrigSig] = useState("");
  const origData = useRef<any>(null);

  const sig = (
    l: Record<string, string>,
    tx: Record<string, string>,
    ic: Record<string, string>,
    st: Record<string, string>,
    p: boolean,
    rp: boolean,
    f: FlatBtn[],
  ) => JSON.stringify([l, tx, ic, st, p, rp, rowsFromFlat(f)]);

  const apply = (d: any) => {
    const li: BtnItem[] = d.items ?? [];
    const ii: InlineItem[] = d.inline ?? [];
    const l = Object.fromEntries(li.map((i) => [i.key, i.value]));
    const tx = Object.fromEntries(ii.map((i) => [i.key, i.text]));
    // icons/styles are shared by inline buttons AND main-menu (reply) buttons.
    const all: { key: string; icon?: string; style?: string }[] = [...ii, ...li];
    const ic = Object.fromEntries(all.map((i) => [i.key, i.icon ?? ""]));
    const st = Object.fromEntries(all.map((i) => [i.key, i.style ?? ""]));
    const p = Boolean(d.premium_enabled);
    const rp = Boolean(d.reply_premium_enabled);
    const f = flatFromRows(d.main_layout ?? []);
    setLabelItems(li);
    setInlineItems(ii);
    setLabels(l);
    setTexts(tx);
    setIcons(ic);
    setStyles(st);
    setPremium(p);
    setReplyPremium(rp);
    setFlat(f);
    setOrigSig(sig(l, tx, ic, st, p, rp, f));
    origData.current = d;
  };

  const dirty =
    !loading &&
    sig(labels, texts, icons, styles, premium, replyPremium, flat) !== origSig;

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
  const enableBtn = (key: string) => setFlat((f) => [...f, { key, brk: true }]);

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

  // antd-token aware colors for .gb-setting-item / .gb-savebar (index.css)
  const cssVars = {
    "--gbst-border": token.colorBorderSecondary,
    "--gbst-bg": token.colorFillQuaternary,
    "--gbst-accent": token.colorPrimary,
    "--gbst-savebar-bg":
      mode === "dark" ? "rgba(27, 31, 39, 0.85)" : "rgba(255, 255, 255, 0.85)",
  } as CSSProperties;

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

  // Live pill preview: current (or default) text + the picked colour; a ✨ marks
  // a premium custom-emoji id (the real emoji can't render outside Telegram).
  const pill = (text: string, styleVal: string, hasIcon: boolean) => {
    const fill = STYLE_FILL[styleVal];
    const base: CSSProperties = fill
      ? { background: fill.bg, color: fill.fg, border: "1px solid transparent" }
      : {
          background: token.colorFillSecondary,
          color: token.colorText,
          border: `1px solid ${token.colorBorderSecondary}`,
        };
    return (
      <span
        style={{
          ...base,
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          maxWidth: "100%",
          padding: "4px 12px",
          borderRadius: 10,
          fontSize: 12.5,
          lineHeight: 1.6,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {hasIcon && <span aria-hidden>✨</span>}
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{text || "—"}</span>
      </span>
    );
  };

  if (loading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
        <Skeleton active paragraph={{ rows: 6 }} style={{ marginTop: 24 }} />
      </Card>
    );
  }

  // ---- main-menu tab -------------------------------------------------------
  const menuRows = rowsFromFlat(flat);
  const menuPreview = (
    <div
      style={{
        background: token.colorFillQuaternary,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 14,
        padding: 10,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      {menuRows.length === 0 && (
        <Text type="secondary" style={{ textAlign: "center", fontSize: 12 }}>
          —
        </Text>
      )}
      {menuRows.map((row, ri) => (
        <div key={ri} style={{ display: "flex", gap: 6 }}>
          {row.map((k) => (
            <div
              key={k}
              style={{
                flex: 1,
                textAlign: "center",
                padding: "8px 6px",
                borderRadius: 10,
                fontSize: 12.5,
                background: token.colorBgElevated,
                border: `1px solid ${token.colorBorderSecondary}`,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {labels[k]?.trim() ||
                labelItems.find((i) => i.key === k)?.default ||
                label(k)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );

  const disabledKeys = EDIT_KEYS.filter((k) => !flat.some((f) => f.key === k));

  const layoutCard = (
    <Card size="small" title={t("buttons.layout_title")} style={{ marginBottom: 16 }}>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message={t("buttons.layout_hint")} />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {flat.map((it, i) => (
              <div key={`${it.key}-${i}`} className="gb-setting-item">
                <Space size={8} style={{ minWidth: 0 }}>
                  {it.brk && i > 0 && <Tag style={{ margin: 0 }}>↵</Tag>}
                  <Text className="gb-setting-label" ellipsis>
                    {label(it.key)}
                  </Text>
                </Space>
                <Space size={4} wrap>
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
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => disableBtn(i)} />
                </Space>
              </div>
            ))}
            {disabledKeys.length > 0 && (
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: "block", margin: "6px 0" }}>
                  {t("buttons.disabled")}
                </Text>
                <Space wrap>
                  {disabledKeys.map((k) => (
                    <Tag
                      key={k}
                      icon={<PlusOutlined />}
                      style={{ cursor: "pointer", padding: "4px 10px", borderStyle: "dashed" }}
                      onClick={() => enableBtn(k)}
                    >
                      {label(k)}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}
          </div>
        </Col>
        <Col xs={24} lg={10}>
          <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
            {t("buttons.menu_preview")}
          </Text>
          {menuPreview}
        </Col>
      </Row>
    </Card>
  );

  const labelCards = (
    <Card size="small" title={t("buttons.labels_title")}>
      <Alert type="warning" showIcon style={{ marginBottom: 12 }} message={t("buttons.reply_premium_hint")} />
      <div className="gb-setting-item" style={{ marginBottom: 16 }}>
        <Text strong className="gb-setting-label">
          {t("buttons.reply_premium_enabled")}
        </Text>
        <Switch checked={replyPremium} onChange={setReplyPremium} />
      </div>
      <Row gutter={[16, 16]}>
        {labelItems.map((it) => (
          <Col xs={24} md={12} xxl={8} key={it.key}>
            <Card
              size="small"
              title={label(it.key)}
              extra={pill(
                (labels[it.key] ?? "").trim() || it.default,
                styles[it.key] ?? "",
                Boolean((icons[it.key] ?? "").trim()) && replyPremium,
              )}
              style={{ height: "100%" }}
            >
              <div style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("buttons.text_label")} ({t("buttons.default")}: {it.default})
                </Text>
              </div>
              <Input
                allowClear
                placeholder={it.default}
                value={labels[it.key] ?? ""}
                onChange={(e) => setLabels((s) => ({ ...s, [it.key]: e.target.value }))}
                style={{ marginBottom: 10 }}
              />
              {it.key !== "admin_menu" && (
                <Row gutter={8}>
                  <Col xs={24} sm={14}>
                    <Input
                      allowClear
                      placeholder={t("buttons.emoji_id_ph")}
                      value={icons[it.key] ?? ""}
                      onChange={(e) => setIcons((s) => ({ ...s, [it.key]: e.target.value }))}
                      disabled={!replyPremium}
                    />
                  </Col>
                  <Col xs={24} sm={10} style={{ marginTop: 0 }}>
                    <Select
                      style={{ width: "100%" }}
                      options={styleOpts}
                      value={styles[it.key] ?? ""}
                      onChange={(v) => setStyles((s) => ({ ...s, [it.key]: v }))}
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
  );

  // ---- inline tab ----------------------------------------------------------
  const q = search.trim().toLowerCase();
  const filtered = inlineItems.filter(
    (it) =>
      !q ||
      it.key.toLowerCase().includes(q) ||
      String(it.label || "").toLowerCase().includes(q) ||
      label(it.key).toLowerCase().includes(q),
  );
  const cats = CAT_ORDER.filter((c) => filtered.some((it) => catOf(it.key) === c));

  const renderInlineCard = (it: InlineItem) => (
    <Col xs={24} md={12} xxl={8} key={it.key}>
      <Card
        size="small"
        title={label(it.key)}
        extra={pill(
          (texts[it.key] ?? "").trim() || it.label,
          styles[it.key] ?? "",
          Boolean((icons[it.key] ?? "").trim()) && premium,
        )}
        style={{ height: "100%" }}
      >
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
          <Col xs={24} sm={14}>
            <Input
              allowClear
              placeholder={t("buttons.emoji_id_ph")}
              value={icons[it.key] ?? ""}
              onChange={(e) => setIcons((s) => ({ ...s, [it.key]: e.target.value }))}
              disabled={!premium}
            />
          </Col>
          <Col xs={24} sm={10}>
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

  const inlineTab = (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message={t("buttons.premium_hint")} />
      <div
        className="gb-setting-item"
        style={{ marginBottom: 16, flexWrap: "wrap", rowGap: 10 }}
      >
        <Space size={10}>
          <Switch checked={premium} onChange={setPremium} />
          <Text strong className="gb-setting-label">
            {t("buttons.premium_enabled")}
          </Text>
        </Space>
        <Input.Search
          allowClear
          placeholder={t("buttons.search_ph")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280, minWidth: 180 }}
        />
      </div>
      {!filtered.length ? (
        <Empty description={t("buttons.noMatch")} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Collapse
          ghost
          defaultActiveKey={cats}
          items={cats.map((c) => ({
            key: c,
            label: (
              <Space size={8}>
                <Text strong>{t(`buttons.cat_${c}`, c)}</Text>
                <Badge
                  count={filtered.filter((it) => catOf(it.key) === c).length}
                  color={token.colorPrimary}
                  size="small"
                />
              </Space>
            ),
            children: (
              <Row gutter={[16, 16]}>
                {filtered.filter((it) => catOf(it.key) === c).map(renderInlineCard)}
              </Row>
            ),
          }))}
        />
      )}
    </>
  );

  const tabItems = [
    {
      key: "menu",
      label: (
        <Space size={6}>
          <AppstoreOutlined />
          {t("buttons.tab_menu")}
        </Space>
      ),
      children: (
        <>
          {layoutCard}
          {labelCards}
        </>
      ),
    },
    {
      key: "inline",
      label: (
        <Space size={6}>
          <ThunderboltOutlined />
          {t("buttons.tab_inline")}
        </Space>
      ),
      children: inlineTab,
    },
  ];

  return (
    <Card style={cssVars}>
      <PageHeader title={t("buttons.title")} subtitle={t("buttons.subtitle")} />
      <Tabs defaultActiveKey="menu" items={tabItems} />
      <div className="gb-savebar" style={{ justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <Text type={dirty ? "warning" : "secondary"} style={{ fontSize: 12.5 }}>
          {dirty ? t("buttons.unsaved") : " "}
        </Text>
        <Space>
          {dirty && (
            <Button icon={<UndoOutlined />} onClick={() => apply(origData.current)}>
              {t("buttons.discard")}
            </Button>
          )}
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={!dirty}
            onClick={save}
          >
            {t("buttons.save")}
          </Button>
        </Space>
      </div>
    </Card>
  );
}
