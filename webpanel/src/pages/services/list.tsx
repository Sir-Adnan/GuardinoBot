import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useList } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtToman } from "../../utils/format";
import { api } from "../../providers/axios";

const gb = (b: number) =>
  b ? `${(b / 1073741824).toFixed(b % 1073741824 ? 1 : 0)} GB` : "∞";

export function ServiceList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { data, isLoading, refetch } = useList<any>({
    resource: "services",
    pagination: { current: 1, pageSize: 100 },
  });

  const [editing, setEditing] = useState<any | null>(null);
  const [icon, setIcon] = useState("");
  const [style, setStyle] = useState("");
  const [saving, setSaving] = useState(false);

  const openEdit = (r: any) => {
    setEditing(r);
    setIcon(r.button_icon ?? "");
    setStyle(r.button_style ?? "");
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await api.patch(`/services/${editing.id}/button`, {
        button_icon: icon,
        button_style: style,
      });
      message.success(t("services.btn_saved"));
      setEditing(null);
      refetch();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const styleOpts = [
    { value: "", label: t("services.btn_no_color") },
    { value: "primary", label: t("buttons.style_primary") },
    { value: "success", label: t("buttons.style_success") },
    { value: "danger", label: t("buttons.style_danger") },
  ];

  const columns = [
    { title: t("services.id"), dataIndex: "id", width: 70, className: "mono" },
    {
      title: t("services.name"),
      dataIndex: "name",
      render: (v: string, r: any) => (
        <Space size={4}>
          {r.button_icon && <Tag color="purple">★</Tag>}
          {v}
        </Space>
      ),
    },
    {
      title: t("services.server"),
      dataIndex: "server_name",
      render: (v: string) => v || "—",
    },
    {
      title: t("services.dataLimit"),
      dataIndex: "data_limit",
      className: "mono",
      render: (v: number) => gb(v),
    },
    {
      title: t("services.duration"),
      dataIndex: "expire_duration",
      className: "mono",
      render: (v: number) => (v ? `${Math.round(v / 86400)} ${t("services.days")}` : "∞"),
    },
    {
      title: t("services.price"),
      dataIndex: "price",
      className: "mono",
      render: (v: number) => fmtToman(v),
    },
    {
      title: t("services.status"),
      key: "status",
      render: (_: any, r: any) => (
        <Space size={4} wrap>
          {r.purchaseable ? (
            <Tag color="green">{t("services.purchaseable")}</Tag>
          ) : (
            <Tag>{t("services.disabled")}</Tag>
          )}
          {r.is_test_service && <Tag color="gold">{t("services.test")}</Tag>}
          {r.resellers_only && <Tag color="blue">{t("services.resellersOnly")}</Tag>}
        </Space>
      ),
    },
    {
      title: t("services.actions"),
      key: "actions",
      width: 110,
      render: (_: any, r: any) => (
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
          {t("services.btn_edit")}
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 940 }}
        pagination={false}
      />
      <Modal
        open={!!editing}
        title={`${t("services.btn_edit")} — ${editing?.name ?? ""}`}
        onCancel={() => setEditing(null)}
        onOk={save}
        confirmLoading={saving}
        okText={t("buttons.save")}
      >
        <p style={{ color: "#888", fontSize: 13 }}>{t("services.btn_hint")}</p>
        <div style={{ marginBottom: 6 }}>{t("services.btn_icon")}</div>
        <Input
          allowClear
          placeholder={t("buttons.emoji_id_ph")}
          value={icon}
          onChange={(e) => setIcon(e.target.value)}
          style={{ marginBottom: 14 }}
        />
        <div style={{ marginBottom: 6 }}>{t("services.btn_style")}</div>
        <Select
          style={{ width: "100%" }}
          options={styleOpts}
          value={style}
          onChange={setStyle}
        />
      </Modal>
    </Card>
  );
}
