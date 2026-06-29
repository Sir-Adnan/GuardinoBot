import { useEffect, useState } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Row,
  Skeleton,
  Switch,
  Tag,
  Typography,
} from "antd";
import { DeleteOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Text } = Typography;

interface Coin {
  code?: string;
  label: string;
  network: string;
  address: string;
  enabled: boolean;
}

/**
 * Offline (manual) crypto gateway editor: enable/title/min + per-coin wallets.
 * The customer picks a coin, pays to its wallet, then submits TXID+screenshot
 * for manual review (bot flow built separately). Saves via PUT
 * /payment-gateways/offline; the bot reloads via settings:dirty.
 */
export function OfflineGateway() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [menuTitle, setMenuTitle] = useState("");
  const [minPay, setMinPay] = useState(0);
  const [requireShot, setRequireShot] = useState(true);
  const [coins, setCoins] = useState<Coin[]>([]);

  const apply = (d: any) => {
    setEnabled(!!d.enabled);
    setMenuTitle(d.menu_title ?? "");
    setMinPay(d.min_pay_amount ?? 0);
    setRequireShot(d.require_screenshot ?? true);
    setCoins(d.coins ?? []);
  };

  useEffect(() => {
    api
      .get("/payment-gateways/offline")
      .then((r) => apply(r.data))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setCoin = (i: number, field: keyof Coin, val: any) =>
    setCoins((c) => c.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));
  const addCoin = () =>
    setCoins((c) => [...c, { label: "", network: "", address: "", enabled: true }]);
  const removeCoin = (i: number) => setCoins((c) => c.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/payment-gateways/offline", {
        enabled,
        menu_title: menuTitle,
        min_pay_amount: minPay,
        require_screenshot: requireShot,
        coins: coins.filter((c) => c.label.trim() && c.address.trim()),
      });
      apply(r.data);
      message.success(t("gateways.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card style={{ marginTop: 16 }}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  return (
    <Card
      style={{ marginTop: 16 }}
      title={
        <span>
          {t("gateways.offline_title")} <Tag color="gold">offline</Tag>
        </span>
      }
      extra={
        <Button
          type="primary"
          size="small"
          icon={<SaveOutlined />}
          loading={saving}
          onClick={save}
        >
          {t("gateways.save")}
        </Button>
      }
    >
      <Alert type="info" showIcon style={{ marginBottom: 14 }} message={t("gateways.offline_hint")} />
      <Row gutter={[16, 12]} style={{ marginBottom: 8 }}>
        <Col xs={24} sm={8}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, height: 32 }}>
            <Switch checked={enabled} onChange={setEnabled} />
            <Text>{t("gateways.f_enabled")}</Text>
          </div>
        </Col>
        <Col xs={24} sm={8}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, height: 32 }}>
            <Switch checked={requireShot} onChange={setRequireShot} />
            <Text>{t("gateways.f_require_screenshot")}</Text>
          </div>
        </Col>
      </Row>
      <Row gutter={[16, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} sm={12}>
          <Text type="secondary" style={{ fontSize: 12 }}>{t("gateways.f_menu_title")}</Text>
          <Input value={menuTitle} onChange={(e) => setMenuTitle(e.target.value)} />
        </Col>
        <Col xs={24} sm={12}>
          <Text type="secondary" style={{ fontSize: 12 }}>{t("gateways.f_min_pay_amount")}</Text>
          <InputNumber style={{ width: "100%" }} min={0} value={minPay} onChange={(v) => setMinPay(Number(v) || 0)} />
        </Col>
      </Row>

      <Text strong style={{ display: "block", marginBottom: 8 }}>{t("gateways.coins")}</Text>
      <div style={{ display: "grid", gap: 8 }}>
        {coins.map((c, i) => (
          <Row key={i} gutter={[8, 8]} align="middle">
            <Col xs={24} md={6}>
              <Input
                placeholder={t("gateways.coin_label")}
                value={c.label}
                onChange={(e) => setCoin(i, "label", e.target.value)}
              />
            </Col>
            <Col xs={24} md={5}>
              <Input
                placeholder={t("gateways.coin_network")}
                value={c.network}
                onChange={(e) => setCoin(i, "network", e.target.value)}
              />
            </Col>
            <Col xs={24} md={9}>
              <Input
                placeholder={t("gateways.coin_address")}
                value={c.address}
                onChange={(e) => setCoin(i, "address", e.target.value)}
              />
            </Col>
            <Col xs={12} md={2}>
              <Switch
                checkedChildren="✓"
                checked={c.enabled}
                onChange={(v) => setCoin(i, "enabled", v)}
              />
            </Col>
            <Col xs={12} md={2} style={{ textAlign: "end" }}>
              <Button danger block icon={<DeleteOutlined />} onClick={() => removeCoin(i)} />
            </Col>
          </Row>
        ))}
        {coins.length === 0 && <Text type="secondary">{t("gateways.no_coins")}</Text>}
      </div>
      <Button icon={<PlusOutlined />} onClick={addCoin} style={{ marginTop: 12 }}>
        {t("gateways.add_coin")}
      </Button>
    </Card>
  );
}
