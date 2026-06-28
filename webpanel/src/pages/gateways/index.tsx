import { useEffect, useState } from "react";
import {
  Alert,
  App as AntdApp,
  Avatar,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { PageHeader } from "../../components/PageHeader";
import { OfflineGateway } from "./OfflineGateway";
import { OfflinePending } from "./OfflinePending";

const { Text } = Typography;

interface Field {
  name: string;
  kind: "bool" | "int" | "str" | "list_str" | "secret";
  value?: any;
  is_set?: boolean;
  hint?: string;
}
interface Gateway {
  key: string;
  name: string;
  type: string;
  fields: Field[];
}
interface PlisioCurrency {
  cid: string;
  currency?: string;
  name?: string;
  icon?: string;
  hidden?: number;
  maintenance?: boolean;
}

const flabel = (t: (k: string) => string, name: string) => {
  const k = `gateways.f_${name}`;
  const tr = t(k);
  return tr === k ? name : tr;
};

export function GatewaysPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [edits, setEdits] = useState<Record<string, Record<string, any>>>({});
  const [plisioCurrencies, setPlisioCurrencies] = useState<PlisioCurrency[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const apply = (gws: Gateway[]) => {
    setGateways(gws);
    const init: Record<string, Record<string, any>> = {};
    gws.forEach((g) => {
      init[g.key] = {};
      g.fields.forEach((f) => {
        const value =
          g.key === "payment_plisio" &&
          f.name === "default_currency" &&
          f.value &&
          !String(f.value).toUpperCase().startsWith("USDT")
            ? "USDT_BSC"
            : f.value;
        // non-secret fields seed from the current value; secrets start empty
        init[g.key][f.name] = f.kind === "secret" ? "" : value;
      });
    });
    setEdits(init);
  };

  useEffect(() => {
    api
      .get("/payment-gateways")
      .then((r) => apply(r.data.gateways ?? []))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    api
      .get("/payment-gateways/plisio/currencies")
      .then((r) => setPlisioCurrencies(r.data.items ?? []))
      .catch(() => setPlisioCurrencies([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setField = (gw: string, name: string, val: any) =>
    setEdits((s) => ({ ...s, [gw]: { ...s[gw], [name]: val } }));

  const save = async (g: Gateway) => {
    setSavingKey(g.key);
    try {
      // send all edited values; the backend treats empty secrets as "no change"
      const r = await api.patch("/payment-gateways", { key: g.key, values: edits[g.key] });
      apply(r.data.gateways ?? []);
      message.success(t("gateways.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  const renderField = (g: Gateway, f: Field) => {
    const val = edits[g.key]?.[f.name];
    const common = { style: { width: "100%" } as const };
    const currencyOptions = plisioCurrencies.map((c) => ({
      value: c.cid,
      label: `${c.cid} ${c.name || ""}`.trim(),
      currencyData: c,
      disabled: !!c.hidden || !!c.maintenance,
    }));
    const usdtCurrencyOptions = currencyOptions.filter((c) =>
      String(c.value).toUpperCase().startsWith("USDT"),
    );
    const currencyOption = (option: any) => {
      const c = option.data?.currencyData || option.currencyData || {};
      return (
        <Space>
          {c.icon ? <Avatar size={18} src={c.icon} /> : <Avatar size={18}>{String(option.value || "?").slice(0, 1)}</Avatar>}
          <span className="mono">{option.value}</span>
          <Text type="secondary">{c.name}</Text>
          {(c.hidden || c.maintenance) && <Tag color="orange">off</Tag>}
        </Space>
      );
    };
    if (g.key === "payment_plisio" && f.name === "default_currency") {
      return (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>{flabel(t, f.name)}</Text>
          <Select
            {...common}
            showSearch
            optionFilterProp="label"
            value={val || "USDT_BSC"}
            options={usdtCurrencyOptions.length ? usdtCurrencyOptions : currencyOptions}
            optionRender={currencyOption}
            onChange={(v) => setField(g.key, f.name, v)}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t("gateways.plisio_base_hint")}
          </Text>
        </>
      );
    }
    if (g.key === "payment_plisio" && f.name === "allowed_currencies") {
      const current = Array.isArray(val)
        ? val
        : typeof val === "string" && val
          ? val.split(",").map((x) => x.trim()).filter(Boolean)
          : ["USDT_BSC", "USDT_TRX", "USDT_TON", "TRX", "TON", "LTC"];
      return (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>{flabel(t, f.name)}</Text>
          <Select
            {...common}
            mode="multiple"
            showSearch
            optionFilterProp="label"
            value={current}
            options={currencyOptions}
            optionRender={currencyOption}
            onChange={(v) => setField(g.key, f.name, v)}
          />
        </>
      );
    }
    if (f.kind === "bool") {
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 10, height: 32 }}>
          <Switch checked={!!val} onChange={(v) => setField(g.key, f.name, v)} />
          <Text>{flabel(t, f.name)}</Text>
        </div>
      );
    }
    if (f.kind === "int") {
      return (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>{flabel(t, f.name)}</Text>
          <InputNumber
            {...common}
            min={0}
            value={val}
            onChange={(v) => setField(g.key, f.name, v)}
          />
        </>
      );
    }
    if (f.kind === "secret") {
      return (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {flabel(t, f.name)}{" "}
            {f.is_set ? (
              <Tag color="green">{t("gateways.secret_set")} {f.hint}</Tag>
            ) : (
              <Tag color="red">{t("gateways.secret_unset")}</Tag>
            )}
          </Text>
          <Input.Password
            {...common}
            allowClear
            autoComplete="new-password"
            placeholder={t("gateways.secret_ph")}
            value={val}
            onChange={(e) => setField(g.key, f.name, e.target.value)}
          />
        </>
      );
    }
    if (f.kind === "list_str") {
      const current = Array.isArray(val)
        ? val
        : typeof val === "string" && val
          ? val.split(",").map((x) => x.trim()).filter(Boolean)
          : [];
      return (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>{flabel(t, f.name)}</Text>
          <Select
            {...common}
            mode="tags"
            value={current}
            onChange={(v) => setField(g.key, f.name, v)}
          />
        </>
      );
    }
    return (
      <>
        <Text type="secondary" style={{ fontSize: 12 }}>{flabel(t, f.name)}</Text>
        <Input
          {...common}
          allowClear
          value={val ?? ""}
          onChange={(e) => setField(g.key, f.name, e.target.value)}
        />
      </>
    );
  };

  return (
    <div>
      <PageHeader title={t("gateways.title")} subtitle={t("gateways.subtitle")} />
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message={t("gateways.hint")} />
      <Row gutter={[16, 16]}>
        {gateways.map((g) => (
          <Col xs={24} lg={12} key={g.key}>
            <Card
              title={
                <span>
                  {g.name} <Tag>{g.type}</Tag>
                </span>
              }
              extra={
                <Button
                  type="primary"
                  size="small"
                  icon={<SaveOutlined />}
                  loading={savingKey === g.key}
                  onClick={() => save(g)}
                >
                  {t("gateways.save")}
                </Button>
              }
            >
              <div style={{ display: "grid", gap: 12 }}>
                {g.fields.map((f) => (
                  <div key={f.name}>{renderField(g, f)}</div>
                ))}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <OfflineGateway />
      <OfflinePending />
    </div>
  );
}
