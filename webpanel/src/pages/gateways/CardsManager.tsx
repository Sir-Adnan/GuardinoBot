import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import {
  CreditCardOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ResponsiveTable } from "../../components/ResponsiveTable";

const { Text } = Typography;

interface CardRow {
  id: number;
  card_number: string;
  card_holder: string;
  is_active: boolean;
}

// 6037-9918-… readable grouping for the table (value stays digits-only)
const groupPan = (v: string) => (v || "").replace(/(\d{4})(?=\d)/g, "$1-");

/** Destination-card CRUD for the card-to-card gateway (super-admin). The bot
 * reads the `cards` table live, so changes apply without a restart. */
export function CardsManager() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [rows, setRows] = useState<CardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<CardRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();

  const load = () =>
    api
      .get("/payment-gateways/cards")
      .then((r) => setRows(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")));

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openModal = (row: CardRow | null) => {
    setEditing(row);
    form.setFieldsValue(
      row
        ? { card_number: row.card_number, card_holder: row.card_holder, is_active: row.is_active }
        : { card_number: "", card_holder: "", is_active: true },
    );
    setOpen(true);
  };

  const save = async (v: any) => {
    setBusy(true);
    try {
      const payload = {
        card_number: String(v.card_number || "").replace(/\D/g, ""),
        card_holder: v.card_holder,
        is_active: !!v.is_active,
      };
      if (editing) await api.patch(`/payment-gateways/cards/${editing.id}`, payload);
      else await api.post("/payment-gateways/cards", payload);
      message.success(t("actions.done"));
      setOpen(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (row: CardRow, active: boolean) => {
    try {
      await api.patch(`/payment-gateways/cards/${row.id}`, { is_active: active });
      setRows((rs) => rs.map((x) => (x.id === row.id ? { ...x, is_active: active } : x)));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const del = async (row: CardRow) => {
    try {
      await api.delete(`/payment-gateways/cards/${row.id}`);
      message.success(t("actions.deleted"));
      setRows((rs) => rs.filter((x) => x.id !== row.id));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const columns = [
    {
      title: t("gateways.card_number"),
      dataIndex: "card_number",
      render: (v: string) => (
        <Text className="mono" copyable={{ text: v }}>
          {groupPan(v)}
        </Text>
      ),
    },
    { title: t("gateways.card_holder"), dataIndex: "card_holder" },
    {
      title: t("gateways.card_active"),
      dataIndex: "is_active",
      width: 110,
      render: (v: boolean, r: CardRow) => (
        <Switch size="small" checked={v} onChange={(val) => toggle(r, val)} />
      ),
    },
    {
      title: "",
      key: "act",
      width: 90,
      render: (_: any, r: CardRow) => (
        <Space size={2}>
          <Button type="text" icon={<EditOutlined />} onClick={() => openModal(r)} />
          <Popconfirm
            title={t("actions.deleteConfirm")}
            okButtonProps={{ danger: true }}
            onConfirm={() => del(r)}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const activeCount = rows.filter((r) => r.is_active).length;

  return (
    <Card
      className="gb-lift"
      style={{ marginTop: 16, borderRadius: 16 }}
      title={
        <Space size={8} wrap>
          <CreditCardOutlined />
          <span style={{ fontWeight: 600 }}>{t("gateways.cards_title")}</span>
          <Tag color={activeCount ? "success" : "red"}>{activeCount} ✓</Tag>
        </Space>
      }
      extra={
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openModal(null)}>
          {t("gateways.card_add")}
        </Button>
      }
    >
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        {t("gateways.cards_subtitle")}
      </Text>
      <ResponsiveTable
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={rows}
        columns={columns}
        pagination={false}
        scroll={{ x: 480 }}
        locale={{
          emptyText: <Empty description={t("gateways.cards_empty")} image={Empty.PRESENTED_IMAGE_SIMPLE} />,
        }}
      />

      <Modal
        open={open}
        title={editing ? t("gateways.card_edit") : t("gateways.card_add")}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={busy}
        okText={t("gateways.save")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={save} preserve={false}>
          <Form.Item
            name="card_number"
            label={t("gateways.card_number")}
            rules={[
              { required: true },
              {
                validator: (_r, v) =>
                  String(v || "").replace(/\D/g, "").length === 16
                    ? Promise.resolve()
                    : Promise.reject(new Error("16")),
                message: "۱۶ رقم",
              },
            ]}
          >
            <Input className="mono" maxLength={19} placeholder="6037 9918 1234 5678" dir="ltr" />
          </Form.Item>
          <Form.Item name="card_holder" label={t("gateways.card_holder")} rules={[{ required: true }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="is_active" label={t("gateways.card_active")} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
