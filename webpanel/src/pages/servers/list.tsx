import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
} from "antd";
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useGetIdentity } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtNum } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";

const PANEL_COLORS: Record<string, string> = {
  marzban: "blue",
  pasarguard: "purple",
  guardino: "green",
};

export function ServerList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= 2;
  const [form] = Form.useForm();
  const panelType = Form.useWatch("panel_type", form);

  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () =>
    api
      .get("/servers", { params: { per_page: 200 } })
      .then((r) => setRows(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")));

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkHealth = async (id: number) => {
    setChecking(id);
    try {
      const res = await api.get(`/servers/${id}/health`);
      if (res.data.ok)
        message.success(`${t("servers.healthy")} — ${res.data.username ?? ""}`);
      else
        message.error(
          `${t("servers.unhealthy")}${res.data.status_code ? ` (${res.data.status_code})` : ""}`,
        );
    } catch {
      message.error(t("servers.unhealthy"));
    } finally {
      setChecking(null);
    }
  };

  const toggleEnabled = async (id: number, enabled: boolean) => {
    try {
      await api.post(`/servers/${id}/enabled`, { enabled });
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const openAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      panel_type: "marzban",
      https: false,
      link_policy: "master_first",
    });
    setOpen(true);
  };

  const openEdit = async (id: number) => {
    try {
      const r = await api.get(`/servers/${id}`);
      const d = r.data;
      setEditing(d);
      form.resetFields();
      form.setFieldsValue({
        panel_type: d.panel_type,
        name: d.name,
        host: d.host,
        port: d.port ?? undefined,
        https: d.https,
        username: d.username,
        password: "",
        link_policy: d.link_policy || "master_first",
      });
      setOpen(true);
    } catch {
      message.error(t("actions.failed"));
    }
  };

  const submit = async (v: any) => {
    setSaving(true);
    try {
      if (editing) {
        const payload: any = {
          name: v.name || null,
          host: v.host,
          port: v.port ?? null,
          https: !!v.https,
          username: v.username,
          link_policy: v.link_policy,
        };
        if (v.password) payload.password = v.password; // blank = keep current
        await api.patch(`/servers/${editing.id}`, payload);
        message.success(t("servers.saved"));
      } else {
        await api.post("/servers", {
          panel_type: v.panel_type,
          name: v.name || null,
          host: v.host,
          port: v.port ?? null,
          https: !!v.https,
          username: v.username,
          password: v.password,
          link_policy: v.link_policy,
        });
        message.success(t("servers.added"));
      }
      setOpen(false);
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.delete(`/servers/${id}`);
      message.success(t("actions.deleted"));
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const columns = [
    { title: t("servers.id"), dataIndex: "id", width: 70, className: "mono" },
    { title: t("servers.name"), key: "name", render: (_: any, r: any) => r.name || r.host },
    { title: t("servers.host"), dataIndex: "host", className: "mono" },
    {
      title: t("servers.panelType"),
      dataIndex: "panel_type",
      render: (v: string) => <Tag color={PANEL_COLORS[v] || "default"}>{v}</Tag>,
    },
    {
      title: t("servers.proxies"),
      dataIndex: "total_proxies",
      className: "mono",
      render: (v: number) => fmtNum(v),
    },
    {
      title: t("servers.status"),
      dataIndex: "is_enabled",
      render: (v: boolean, r: any) =>
        isAdmin ? (
          <Switch checked={v} onChange={(c) => toggleEnabled(r.id, c)} />
        ) : v ? (
          <Tag color="green">{t("servers.enabled")}</Tag>
        ) : (
          <Tag>{t("servers.disabled")}</Tag>
        ),
    },
    {
      title: t("services.actions"),
      key: "actions",
      width: 170,
      render: (_: any, r: any) => (
        <Space size={2}>
          <Tooltip title={t("servers.health")}>
            <Button
              size="small"
              icon={<ApiOutlined />}
              loading={checking === r.id}
              onClick={() => checkHealth(r.id)}
            />
          </Tooltip>
          <Tooltip title={t("servers.edit")}>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r.id)} />
          </Tooltip>
          <Popconfirm
            title={t("servers.deleteConfirm")}
            okButtonProps={{ danger: true }}
            onConfirm={() => remove(r.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <PageHeader
        title={t("servers.title")}
        subtitle={t("servers.subtitle")}
        extra={
          isAdmin && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
              {t("servers.add")}
            </Button>
          )
        }
      />
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={columns}
        scroll={{ x: 880 }}
        pagination={false}
      />

      <Modal
        open={open}
        title={editing ? t("servers.editTitle") : t("servers.addTitle")}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText={editing ? t("servers.save") : t("servers.connect")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={submit} preserve={false}>
          <Form.Item name="panel_type" label={t("servers.panelType")} rules={[{ required: true }]}>
            <Select
              disabled={!!editing}
              options={[
                { value: "marzban", label: "Marzban" },
                { value: "pasarguard", label: "PasarGuard" },
                { value: "guardino", label: "Guardino" },
              ]}
            />
          </Form.Item>
          <Form.Item name="name" label={t("servers.name")}>
            <Input maxLength={200} placeholder={t("servers.namePh")} />
          </Form.Item>
          <Space style={{ display: "flex" }} align="end" wrap>
            <Form.Item name="host" label={t("servers.host")} rules={[{ required: true }]} style={{ flex: 1, minWidth: 220 }}>
              <Input placeholder="panel.example.com" />
            </Form.Item>
            <Form.Item name="port" label={t("servers.port")}>
              <InputNumber min={1} max={65535} style={{ width: 110 }} />
            </Form.Item>
            <Form.Item name="https" label="HTTPS" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Space style={{ display: "flex" }} align="start" wrap>
            <Form.Item name="username" label={t("servers.username")} rules={[{ required: true }]} style={{ flex: 1, minWidth: 200 }}>
              <Input autoComplete="off" />
            </Form.Item>
            <Form.Item
              name="password"
              label={t("servers.password")}
              rules={editing ? [] : [{ required: true }]}
              style={{ flex: 1, minWidth: 200 }}
            >
              <Input.Password
                autoComplete="new-password"
                placeholder={editing ? t("servers.passwordKeep") : ""}
              />
            </Form.Item>
          </Space>
          {panelType === "guardino" && (
            <Form.Item name="link_policy" label={t("servers.linkPolicy")}>
              <Select
                options={[
                  { value: "master_first", label: t("servers.lp_master") },
                  { value: "node_first", label: t("servers.lp_node") },
                ]}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Card>
  );
}
