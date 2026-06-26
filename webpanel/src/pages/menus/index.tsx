import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Title, Text } = Typography;

interface Menu {
  id: number;
  title: string;
  parent_id: number | null;
  purchase: boolean;
  renew: boolean;
  resellers_only: boolean;
  users_only: boolean;
  services_count: number;
  children_count: number;
}

export function MenusPage() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm();
  const [menus, setMenus] = useState<Menu[]>([]);
  const [services, setServices] = useState<{ id: number; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Menu | null>(null);
  const [saving, setSaving] = useState(false);

  const loadMenus = () =>
    api
      .get("/menus")
      .then((r) => setMenus(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")));

  useEffect(() => {
    Promise.all([
      loadMenus(),
      api
        .get("/services", { params: { per_page: 200 } })
        .then((r) => setServices(r.data.items ?? []))
        .catch(() => undefined),
    ]).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const titleOf = (id: number | null) =>
    id == null ? "—" : menus.find((m) => m.id === id)?.title ?? `#${id}`;

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      purchase: true,
      renew: true,
      resellers_only: false,
      users_only: false,
      service_ids: [],
    });
    setOpen(true);
  };

  const openEdit = async (m: Menu) => {
    try {
      const r = await api.get(`/menus/${m.id}`);
      setEditing(m);
      form.resetFields();
      form.setFieldsValue({
        title: r.data.title,
        description: r.data.description,
        parent_id: r.data.parent_id ?? undefined,
        purchase: r.data.purchase,
        renew: r.data.renew,
        resellers_only: r.data.resellers_only,
        users_only: r.data.users_only,
        service_ids: r.data.service_ids ?? [],
        button_icon: r.data.button_icon ?? "",
        button_style: r.data.button_style ?? "",
      });
      setOpen(true);
    } catch {
      message.error(t("actions.failed"));
    }
  };

  const submit = async (v: any) => {
    setSaving(true);
    const payload = {
      title: v.title,
      description: v.description || null,
      parent_id: v.parent_id ?? null,
      purchase: !!v.purchase,
      renew: !!v.renew,
      resellers_only: !!v.resellers_only,
      users_only: !!v.users_only,
      service_ids: v.service_ids ?? [],
      button_icon: v.button_icon || "",
      button_style: v.button_style || "",
    };
    try {
      if (editing) await api.patch(`/menus/${editing.id}`, payload);
      else await api.post("/menus", payload);
      message.success(t(editing ? "menus.saved" : "menus.created"));
      setOpen(false);
      await loadMenus();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (m: Menu) => {
    try {
      await api.delete(`/menus/${m.id}`);
      message.success(t("actions.deleted"));
      await loadMenus();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const columns = [
    { title: t("menus.titleCol"), dataIndex: "title" },
    {
      title: t("menus.parent"),
      dataIndex: "parent_id",
      render: (v: number | null) => titleOf(v),
    },
    {
      title: t("menus.flags"),
      render: (_: any, m: Menu) => (
        <Space size={4} wrap>
          {!m.purchase && <Tag>{t("menus.noPurchase")}</Tag>}
          {!m.renew && <Tag>{t("menus.noRenew")}</Tag>}
          {m.resellers_only && <Tag color="purple">{t("menus.resellersOnly")}</Tag>}
          {m.users_only && <Tag color="cyan">{t("menus.usersOnly")}</Tag>}
        </Space>
      ),
    },
    {
      title: t("menus.services"),
      dataIndex: "services_count",
      width: 90,
      className: "mono",
    },
    {
      title: t("menus.children"),
      dataIndex: "children_count",
      width: 90,
      className: "mono",
    },
    {
      title: "",
      width: 110,
      render: (_: any, m: Menu) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(m)}
          />
          <Popconfirm
            title={t("menus.deleteConfirm")}
            okButtonProps={{ danger: true }}
            onConfirm={() => remove(m)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          marginBottom: 16,
          gap: 12,
        }}
      >
        <div style={{ flex: 1 }}>
          <Title level={4} style={{ margin: 0 }}>
            {t("menus.title")}
          </Title>
          <Text type="secondary">{t("menus.subtitle")}</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          {t("menus.new")}
        </Button>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={menus}
        columns={columns}
        scroll={{ x: 760 }}
        pagination={false}
      />

      <Modal
        open={open}
        title={editing ? t("menus.editTitle") : t("menus.new")}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText={t("menus.save")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={submit} preserve={false}>
          <Form.Item
            name="title"
            label={t("menus.titleCol")}
            rules={[{ required: true }]}
          >
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item name="parent_id" label={t("menus.parent")}>
            <Select
              allowClear
              placeholder={t("menus.rootLevel")}
              options={menus
                .filter((m) => !editing || m.id !== editing.id)
                .map((m) => ({ value: m.id, label: m.title }))}
            />
          </Form.Item>
          <Form.Item name="service_ids" label={t("menus.services")}>
            <Select
              mode="multiple"
              allowClear
              optionFilterProp="label"
              placeholder={t("menus.servicesHint")}
              options={services.map((s) => ({ value: s.id, label: s.name }))}
            />
          </Form.Item>
          <Form.Item name="description" label={t("menus.description")}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} dir="auto" />
          </Form.Item>
          <Space.Compact block>
            <Form.Item
              name="button_icon"
              label={t("menus.btn_icon")}
              style={{ flex: 1, marginInlineEnd: 8 }}
              tooltip={t("menus.btn_hint")}
            >
              <Input allowClear placeholder={t("buttons.emoji_id_ph")} />
            </Form.Item>
            <Form.Item
              name="button_style"
              label={t("menus.btn_style")}
              style={{ width: 160 }}
            >
              <Select
                options={[
                  { value: "", label: t("services.btn_no_color") },
                  { value: "primary", label: t("buttons.style_primary") },
                  { value: "success", label: t("buttons.style_success") },
                  { value: "danger", label: t("buttons.style_danger") },
                ]}
              />
            </Form.Item>
          </Space.Compact>
          <Space size="large" wrap>
            <Form.Item name="purchase" label={t("menus.purchase")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="renew" label={t("menus.renew")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="resellers_only"
              label={t("menus.resellersOnly")}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="users_only"
              label={t("menus.usersOnly")}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  );
}
