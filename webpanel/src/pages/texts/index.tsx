import { useContext, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  App as AntdApp,
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  theme as antdTheme,
} from "antd";
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";
import { ColorModeContext } from "../../contexts/color-mode";

const { Text } = Typography;

interface TextItem {
  key: string;
  value: string;
  variables: string[];
  group: string;
}

const GROUP_ORDER = ["general", "sales", "support", "access", "alerts"];

export function TextsPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { token } = antdTheme.useToken();
  const { mode } = useContext(ColorModeContext);
  const [items, setItems] = useState<TextItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savingAll, setSavingAll] = useState(false);
  const [search, setSearch] = useState("");
  const [previewKeys, setPreviewKeys] = useState<Set<string>>(new Set());
  const taRefs = useRef<Record<string, any>>({});

  const togglePreview = (key: string) =>
    setPreviewKeys((s) => {
      const next = new Set(s);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // insert {VAR} at the textarea cursor (falls back to appending)
  const insertVar = (key: string, v: string) => {
    const token_ = `{${v}}`;
    const ta = taRefs.current[key]?.resizableTextArea?.textArea as
      | HTMLTextAreaElement
      | undefined;
    setDrafts((d) => {
      const cur = d[key] ?? "";
      if (ta && typeof ta.selectionStart === "number") {
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        requestAnimationFrame(() => {
          ta.focus();
          ta.setSelectionRange(start + token_.length, start + token_.length);
        });
        return { ...d, [key]: cur.slice(0, start) + token_ + cur.slice(end) };
      }
      return { ...d, [key]: cur + token_ };
    });
  };

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

  const save = async (key: string, silent = false): Promise<boolean> => {
    setSavingKey(key);
    try {
      const r = await api.patch("/texts", { key, value: drafts[key] ?? "" });
      setItems((arr) => arr.map((i) => (i.key === key ? { ...i, value: r.data.value } : i)));
      setDrafts((d) => ({ ...d, [key]: r.data.value }));
      if (!silent) message.success(t("texts.saved"));
      return true;
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
      return false;
    } finally {
      setSavingKey(null);
    }
  };

  const isDirty = (i: TextItem) => (drafts[i.key] ?? "") !== i.value;
  const dirtyItems = items.filter(isDirty);

  const saveAll = async () => {
    setSavingAll(true);
    let ok = 0;
    for (const i of dirtyItems) {
      if (await save(i.key, true)) ok += 1;
    }
    setSavingAll(false);
    if (ok) message.success(t("texts.saved"));
  };

  const label = (key: string) => {
    const k = `texts.k.${key}`;
    const tr = t(k);
    return tr === k ? key : tr;
  };

  const groups = useMemo(() => {
    const present = GROUP_ORDER.filter((g) => items.some((i) => i.group === g));
    const extra = [...new Set(items.map((i) => i.group))].filter((g) => !GROUP_ORDER.includes(g));
    return [...present, ...extra];
  }, [items]);

  // antd-token aware colors for .gb-setting-item / .gb-savebar (index.css)
  const cssVars = {
    "--gbst-border": token.colorBorderSecondary,
    "--gbst-bg": token.colorFillQuaternary,
    "--gbst-accent": token.colorPrimary,
    "--gbst-savebar-bg":
      mode === "dark" ? "rgba(27, 31, 39, 0.85)" : "rgba(255, 255, 255, 0.85)",
  } as CSSProperties;

  if (loading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
        <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
          {[0, 1, 2, 3].map((i) => (
            <Col xs={24} xl={12} key={i}>
              <Card size="small">
                <Skeleton active paragraph={{ rows: 4 }} />
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    );
  }

  const renderCard = (it: TextItem) => {
    const val = drafts[it.key] ?? "";
    const dirty = val !== it.value;
    const showPreview = previewKeys.has(it.key);
    return (
      <Col xs={24} xl={12} key={it.key}>
        <Card
          title={
            <Space size={8}>
              {label(it.key)}
              {dirty && (
                <Tag color="warning" style={{ margin: 0, fontSize: 11 }}>
                  {t("texts.unsaved")}
                </Tag>
              )}
            </Space>
          }
          size="small"
          style={{ height: "100%" }}
          extra={
            <span style={{ display: "inline-flex", gap: 8 }}>
              <Tooltip title={t("texts.preview")}>
                <Button
                  size="small"
                  icon={showPreview ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={() => togglePreview(it.key)}
                />
              </Tooltip>
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
            </span>
          }
        >
          {it.variables.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary" style={{ marginInlineEnd: 6, fontSize: 12 }}>
                {t("texts.variables")}:
              </Text>
              {it.variables.map((v) => (
                <Tag
                  key={v}
                  className="mono"
                  color="processing"
                  style={{ cursor: "pointer" }}
                  onClick={() => insertVar(it.key, v)}
                >{`{${v}}`}</Tag>
              ))}
              <Text type="secondary" style={{ fontSize: 11, marginInlineStart: 4 }}>
                ({t("texts.clickToInsert")})
              </Text>
            </div>
          )}
          <Input.TextArea
            ref={(el) => {
              taRefs.current[it.key] = el;
            }}
            value={val}
            onChange={(e) => setDrafts((d) => ({ ...d, [it.key]: e.target.value }))}
            autoSize={{ minRows: 3, maxRows: 14 }}
            dir="auto"
          />
          <div style={{ textAlign: "end", marginTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
              {val.length} {t("texts.chars")}
            </Text>
          </div>
          {showPreview && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {t("texts.previewTitle")}
              </Text>
              <div
                style={{
                  marginTop: 6,
                  background: token.colorPrimaryBg,
                  border: `1px solid ${token.colorPrimaryBorder}`,
                  borderRadius: "14px 14px 4px 14px",
                  padding: "10px 14px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  lineHeight: 1.7,
                  fontSize: 14,
                }}
                dangerouslySetInnerHTML={{ __html: val || "—" }}
              />
            </div>
          )}
        </Card>
      </Col>
    );
  };

  const filtered = search
    ? items.filter(
        (i) =>
          i.key.toLowerCase().includes(search.toLowerCase()) ||
          label(i.key).toLowerCase().includes(search.toLowerCase()),
      )
    : null;

  const tabItems = groups.map((g) => {
    const inGroup = items.filter((i) => i.group === g);
    const dirtyCount = inGroup.filter(isDirty).length;
    return {
      key: g,
      label: (
        <Space size={6}>
          {t(`texts.g_${g}`, g)}
          {dirtyCount > 0 && <Badge count={dirtyCount} size="small" color={token.colorWarning} />}
        </Space>
      ),
      children: <Row gutter={[16, 16]}>{inGroup.map(renderCard)}</Row>,
    };
  });

  return (
    <Card style={cssVars}>
      <PageHeader
        title={t("texts.title")}
        subtitle={t("texts.subtitle")}
        extra={
          <Input.Search
            placeholder={t("texts.search")}
            allowClear
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 240 }}
          />
        }
      />
      <div className="gb-setting-item" style={{ marginBottom: 16 }}>
        <Text type="secondary" className="gb-setting-label">
          {t("texts.emoji_hint")}
        </Text>
      </div>
      {filtered ? (
        filtered.length ? (
          <Row gutter={[16, 16]}>{filtered.map(renderCard)}</Row>
        ) : (
          <Empty description={t("texts.noMatch")} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )
      ) : (
        <Tabs items={tabItems} />
      )}
      {dirtyItems.length > 0 && (
        <div className="gb-savebar" style={{ justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <Text type="warning" style={{ fontSize: 12.5 }}>
            {dirtyItems.length} {t("texts.unsaved")}
          </Text>
          <Button type="primary" icon={<SaveOutlined />} loading={savingAll} onClick={saveAll}>
            {t("texts.save_all")}
          </Button>
        </div>
      )}
    </Card>
  );
}
