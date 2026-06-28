import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Image,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  CheckOutlined,
  CloseOutlined,
  PictureOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtToman } from "../../utils/format";

const { Text } = Typography;

/**
 * Pending offline-payment review. Read here; **approve/reject is queued for the
 * bot** (`POST .../review` → Redis → bot credits + notifies + activates), so the
 * web never credits directly. The screenshot is proxied (auth'd blob → object URL).
 */
export function OfflinePending() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<number | null>(null);
  const [shot, setShot] = useState<string | null>(null);

  const load = () =>
    api
      .get("/payment-gateways/offline/pending")
      .then((r) => setItems(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")));

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const review = async (cpId: number, action: "approve" | "reject") => {
    setActing(cpId);
    try {
      await api.post(`/payment-gateways/offline/${cpId}/review`, { action });
      message.success(t("gateways.queued"));
      setItems((s) => s.filter((x) => x.cp_id !== cpId));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setActing(null);
    }
  };

  const viewShot = async (cpId: number) => {
    try {
      const r = await api.get(`/payment-gateways/offline/${cpId}/screenshot`, {
        responseType: "blob",
      });
      setShot(URL.createObjectURL(r.data));
    } catch {
      message.error(t("actions.failed"));
    }
  };

  const columns = [
    {
      title: t("gateways.col_user"),
      dataIndex: "user_id",
      render: (v: number, r: any) => (
        <span className="mono">
          {v}
          {r.username ? ` @${r.username}` : ""}
        </span>
      ),
    },
    {
      title: t("gateways.col_amount"),
      dataIndex: "amount",
      className: "mono",
      render: (v: number) => fmtToman(v),
    },
    {
      title: t("gateways.col_coin"),
      key: "coin",
      render: (_: any, r: any) => (
        <span>
          {r.coin_label} {r.network ? <Tag>{r.network}</Tag> : null}
        </span>
      ),
    },
    {
      title: "TXID",
      dataIndex: "txid",
      render: (v: string) => (
        <Text className="mono" copyable style={{ fontSize: 12 }} ellipsis={{ tooltip: v }}>
          {v}
        </Text>
      ),
    },
    {
      title: t("gateways.col_when"),
      dataIndex: "created_at",
      render: (v: string) => fmtDate(v),
    },
    {
      title: "",
      key: "actions",
      width: 150,
      render: (_: any, r: any) => (
        <Space size={2}>
          {r.has_screenshot && (
            <Button size="small" icon={<PictureOutlined />} onClick={() => viewShot(r.cp_id)} />
          )}
          <Popconfirm title={t("gateways.approve_q")} onConfirm={() => review(r.cp_id, "approve")}>
            <Button size="small" type="primary" icon={<CheckOutlined />} loading={acting === r.cp_id} />
          </Popconfirm>
          <Popconfirm
            title={t("gateways.reject_q")}
            okButtonProps={{ danger: true }}
            onConfirm={() => review(r.cp_id, "reject")}
          >
            <Button size="small" danger icon={<CloseOutlined />} loading={acting === r.cp_id} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      style={{ marginTop: 16 }}
      title={`${t("gateways.pending_title")} (${items.length})`}
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={() => load()}>
          {t("dashboard.refresh")}
        </Button>
      }
    >
      <Table
        rowKey="cp_id"
        size="small"
        loading={loading}
        dataSource={items}
        columns={columns}
        pagination={false}
        scroll={{ x: 720 }}
        locale={{ emptyText: t("gateways.no_pending") }}
      />
      <Image
        style={{ display: "none" }}
        src={shot || undefined}
        preview={{
          visible: !!shot,
          src: shot || undefined,
          onVisibleChange: (v) => {
            if (!v) {
              if (shot) URL.revokeObjectURL(shot);
              setShot(null);
            }
          },
        }}
      />
    </Card>
  );
}
