import { useEffect, useMemo, useRef, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Input,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";

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
  const [items, setItems] = useState<TextItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
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
    const token = `{${v}}`;
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
          ta.setSelectionRange(start + token.length, start + token.length);
        });
        return { ...d, [key]: cur.slice(0, start) + token + cur.slice(end) };
      }
      return { ...d, [key]: cur + token };
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

  const save = async (key: string) => {
    setSavingKey(key);
    try {
      const r = await api.patch("/texts", { key, value: drafts[key] ?? "" });
      setItems((arr) => arr.map((i) => (i.key === key ? { ...i, value: r.data.value } : i)));
      setDrafts((d) => ({ ...d, [key]: r.data.value }));
      message.success(t("texts.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSavingKey(null);
    }
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

  if (loading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 300 }}>
        <Spin />
      </div>
    );
  }

  const renderCard = (it: TextItem) => {
    const val = drafts[it.key] ?? "";
    const dirty = val !== it.value;
    const showPreview = previewKeys.has(it.key);
    return (
      <Card
        key={it.key}
        title={label(it.key)}
        size="small"
        style={{ marginBottom: 16 }}
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
                background: "rgba(16,185,129,0.10)",
                border: "1px solid rgba(16,185,129,0.25)",
                borderRadius: 12,
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
    );
  };

  const filtered = search
    ? items.filter(
        (i) =>
          i.key.toLowerCase().includes(search.toLowerCase()) ||
          label(i.key).toLowerCase().includes(search.toLowerCase()),
      )
    : null;

  const tabItems = groups.map((g) => ({
    key: g,
    label: t(`texts.g_${g}`, g),
    children: <div>{items.filter((i) => i.group === g).map(renderCard)}</div>,
  }));

  return (
    <div>
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
      <Card size="small" style={{ marginBottom: 16 }}>
        <Text type="secondary">{t("texts.emoji_hint")}</Text>
      </Card>
      {filtered ? (
        <div>{filtered.length ? filtered.map(renderCard) : <Text type="secondary">{t("texts.noMatch")}</Text>}</div>
      ) : (
        <Tabs items={tabItems} />
      )}
    </div>
  );
}
