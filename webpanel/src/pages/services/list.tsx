import { useEffect, useState } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

const { Text } = Typography;
const GBYTE = 1073741824;
const toGb = (b: number) => (b ? +(b / GBYTE).toFixed(2) : 0);
const toBytes = (gb: number) => Math.round((gb || 0) * GBYTE);

export function ServiceList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [mode, setMode] = useState<"edit" | "create">("edit");
  const [servers, setServers] = useState<any[]>([]);
  const [serverId, setServerId] = useState<number | undefined>(undefined);
  const [catalog, setCatalog] = useState<any | null>(null);
  const [catLoading, setCatLoading] = useState(false);
  const emptyProv = {
    all_inbounds: false,
    inbound_sel: [] as string[],
    group_ids: [] as number[],
    node_ids: [] as number[],
    pricing_mode: "",
  };
  const [prov, setProv] = useState<any>(emptyProv);

  const load = () =>
    api
      .get("/services", { params: { per_page: 200 } })
      .then((r) => setRows(r.data.items ?? []))
      .catch(() => message.error(t("actions.failed")));

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreate = async () => {
    setMode("create");
    setEditing(null);
    setServerId(undefined);
    setCatalog(null);
    setProv({ ...emptyProv });
    form.resetFields();
    form.setFieldsValue({
      name: "",
      price: 0,
      data_gb: 0,
      expire_days: 0,
      purchaseable: true,
      renewable: true,
      is_test_service: false,
      one_time_only: false,
      resellers_only: false,
      users_only: false,
      create_on_hold_users: false,
      append_available_data_renew: false,
      usage_reset_strategy: "no_reset",
      flow: "",
      button_icon: "",
      button_style: "",
    });
    if (!servers.length) {
      try {
        const r = await api.get("/servers", { params: { per_page: 200 } });
        setServers(r.data.items ?? []);
      } catch {
        /* ignore — picker just stays empty */
      }
    }
    setOpen(true);
  };

  const onServerChange = async (sid: number) => {
    setServerId(sid);
    setCatalog(null);
    setProv({ ...emptyProv });
    setCatLoading(true);
    try {
      const r = await api.get("/services/provisioning", { params: { server_id: sid } });
      setCatalog(r.data);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setCatLoading(false);
    }
  };

  const openEdit = async (id: number) => {
    try {
      setMode("edit");
      const r = await api.get(`/services/${id}`);
      const d = r.data;
      setEditing(d);
      form.resetFields();
      form.setFieldsValue({
        name: d.name,
        price: d.price,
        data_gb: toGb(d.data_limit),
        expire_days: d.expire_duration ? Math.round(d.expire_duration / 86400) : 0,
        purchaseable: d.purchaseable,
        renewable: d.renewable,
        is_test_service: d.is_test_service,
        one_time_only: d.one_time_only,
        resellers_only: d.resellers_only,
        users_only: d.users_only,
        create_on_hold_users: d.create_on_hold_users,
        append_available_data_renew: d.append_available_data_renew,
        usage_reset_strategy: d.usage_reset_strategy || "no_reset",
        flow: d.flow || "",
        button_icon: d.button_icon ?? "",
        button_style: d.button_style ?? "",
      });
      setOpen(true);
    } catch {
      message.error(t("actions.failed"));
    }
  };

  const submit = async (v: any) => {
    const common = {
      name: v.name,
      price: v.price ?? 0,
      data_limit: toBytes(v.data_gb),
      expire_duration: Math.round((v.expire_days || 0) * 86400),
      purchaseable: !!v.purchaseable,
      renewable: !!v.renewable,
      is_test_service: !!v.is_test_service,
      one_time_only: !!v.one_time_only,
      resellers_only: !!v.resellers_only,
      users_only: !!v.users_only,
      create_on_hold_users: !!v.create_on_hold_users,
      append_available_data_renew: !!v.append_available_data_renew,
      usage_reset_strategy: v.usage_reset_strategy,
      flow: v.flow || "",
      button_icon: v.button_icon || "",
      button_style: v.button_style || "",
    };
    setSaving(true);
    try {
      if (mode === "create") {
        if (!serverId) {
          message.error(t("services.pickServer"));
          setSaving(false);
          return;
        }
        const pt = catalog?.panel_type;
        const payload: any = { ...common, server_id: serverId };
        if (pt === "marzban") {
          const inbounds: Record<string, string[]> = {};
          (prov.inbound_sel || []).forEach((s: string) => {
            const i = s.indexOf("::");
            const proto = s.slice(0, i);
            const tag = s.slice(i + 2);
            (inbounds[proto] = inbounds[proto] || []).push(tag);
          });
          payload.all_inbounds = !!prov.all_inbounds;
          payload.inbounds = inbounds;
        } else if (pt === "pasarguard") {
          payload.panel_config = { group_ids: prov.group_ids || [] };
        } else if (pt === "guardino") {
          payload.panel_config = {
            node_ids: prov.node_ids || [],
            pricing_mode: prov.pricing_mode || "",
          };
        }
        await api.post("/services", payload);
        message.success(t("services.created"));
      } else {
        if (!editing) return;
        await api.patch(`/services/${editing.id}`, common);
        message.success(t("services.saved"));
      }
      setOpen(false);
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const duplicate = async (id: number) => {
    try {
      const r = await api.post(`/services/${id}/duplicate`);
      message.success(t("services.duplicated"));
      await load();
      openEdit(r.data.id); // open the new draft for editing
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const remove = async (id: number) => {
    try {
      await api.delete(`/services/${id}`);
      message.success(t("actions.deleted"));
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const move = async (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[i], next[j]] = [next[j], next[i]];
    setRows(next);
    try {
      await api.post("/services/reorder", { ids: next.map((r) => r.id) });
    } catch {
      message.error(t("actions.failed"));
      load();
    }
  };

  const columns = [
    { title: t("services.id"), dataIndex: "id", width: 64, className: "mono" },
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
      render: (v: string, r: any) => (
        <Space size={4}>
          {v || "—"}
          {r.panel_type && (
            <Tag
              color={{ marzban: "blue", pasarguard: "purple", guardino: "green" }[
                r.panel_type as string
              ]}
            >
              {r.panel_type}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: t("services.dataLimit"),
      dataIndex: "data_limit",
      className: "mono",
      render: (v: number) => (v ? `${toGb(v)} GB` : "∞"),
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
      render: (v: number) => <Text strong>{fmtToman(v)}</Text>,
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
      title: t("services.order"),
      key: "order",
      width: 78,
      render: (_: any, __: any, i: number) => (
        <Space size={0}>
          <Button
            type="text"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={i === 0}
            onClick={() => move(i, -1)}
          />
          <Button
            type="text"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={i === rows.length - 1}
            onClick={() => move(i, 1)}
          />
        </Space>
      ),
    },
    {
      title: t("services.actions"),
      key: "actions",
      width: 130,
      render: (_: any, r: any) => (
        <Space size={2}>
          <Tooltip title={t("services.btn_edit_full")}>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r.id)} />
          </Tooltip>
          <Tooltip title={t("services.duplicate")}>
            <Button size="small" icon={<CopyOutlined />} onClick={() => duplicate(r.id)} />
          </Tooltip>
          <Popconfirm
            title={t("services.deleteConfirm")}
            okButtonProps={{ danger: true }}
            onConfirm={() => remove(r.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const flowOpts = [
    { value: "", label: t("services.flow_none") },
    { value: "xtls-rprx-vision", label: "xtls-rprx-vision" },
  ];
  const resetOpts = ["no_reset", "day", "week", "month", "year"].map((k) => ({
    value: k,
    label: t(`services.reset_${k}`),
  }));
  const styleOpts = [
    { value: "", label: t("services.btn_no_color") },
    { value: "primary", label: t("buttons.style_primary") },
    { value: "success", label: t("buttons.style_success") },
    { value: "danger", label: t("buttons.style_danger") },
  ];

  const renderProvisioning = () => {
    const c = catalog?.catalog ?? {};
    const pt = catalog?.panel_type;
    if (pt === "marzban") {
      const opts: any[] = [];
      Object.entries(c).forEach(([proto, tags]: any) => {
        if (Array.isArray(tags))
          tags.forEach((tag: string) =>
            opts.push({ value: `${proto}::${tag}`, label: `${tag} · ${proto}` }),
          );
      });
      return (
        <>
          <Divider orientation="left" plain>
            {t("services.sec_provisioning")} · Marzban
          </Divider>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Switch
              checked={prov.all_inbounds}
              onChange={(val) => setProv((p: any) => ({ ...p, all_inbounds: val }))}
            />
            <Text>{t("services.allInbounds")}</Text>
          </div>
          {!prov.all_inbounds && (
            <Select
              mode="multiple"
              allowClear
              style={{ width: "100%" }}
              placeholder={t("services.pickInbounds")}
              value={prov.inbound_sel}
              onChange={(val) => setProv((p: any) => ({ ...p, inbound_sel: val }))}
              options={opts}
            />
          )}
        </>
      );
    }
    if (pt === "pasarguard") {
      const groups = c.groups ?? [];
      return (
        <>
          <Divider orientation="left" plain>
            {t("services.sec_provisioning")} · PasarGuard
          </Divider>
          <Select
            mode="multiple"
            allowClear
            style={{ width: "100%" }}
            placeholder={t("services.pickGroups")}
            value={prov.group_ids}
            onChange={(val) => setProv((p: any) => ({ ...p, group_ids: val }))}
            options={groups.map((g: any) => ({ value: g.id, label: g.name ?? g.id }))}
          />
        </>
      );
    }
    if (pt === "guardino") {
      const nodes = c.nodes ?? [];
      return (
        <>
          <Divider orientation="left" plain>
            {t("services.sec_provisioning")} · Guardino
          </Divider>
          <Select
            mode="multiple"
            allowClear
            style={{ width: "100%", marginBottom: 10 }}
            placeholder={t("services.pickNodes")}
            value={prov.node_ids}
            onChange={(val) => setProv((p: any) => ({ ...p, node_ids: val }))}
            options={nodes.map((n: any) => ({ value: n.id, label: n.name ?? n.id }))}
          />
          <Select
            allowClear
            style={{ width: "100%" }}
            placeholder={t("services.pricingMode")}
            value={prov.pricing_mode || undefined}
            onChange={(val) => setProv((p: any) => ({ ...p, pricing_mode: val || "" }))}
            options={[
              { value: "bundle", label: "bundle" },
              { value: "per_node", label: "per_node" },
            ]}
          />
        </>
      );
    }
    return null;
  };

  return (
    <Card>
      <PageHeader
        title={t("services.title")}
        subtitle={t("services.subtitle")}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t("services.new")}
          </Button>
        }
      />
      <ResponsiveTable
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={columns}
        scroll={{ x: 1040 }}
        pagination={false}
      />

      <Modal
        open={open}
        title={
          mode === "create"
            ? t("services.new")
            : `${t("services.btn_edit_full")} — ${editing?.name ?? ""}`
        }
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText={mode === "create" ? t("services.create") : t("buttons.save")}
        width={640}
        destroyOnClose
      >
        {editing && (editing.proxies_count > 0 || editing.reserves_count > 0) && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t("services.inUseHint", {
              proxies: editing.proxies_count,
              reserves: editing.reserves_count,
            })}
          </Text>
        )}
        <Form form={form} layout="vertical" onFinish={submit} preserve={false}>
          {mode === "create" && (
            <>
              <Divider orientation="left" plain>
                {t("services.sec_server")}
              </Divider>
              <Select
                showSearch
                optionFilterProp="label"
                placeholder={t("services.pickServer")}
                style={{ width: "100%", maxWidth: 380 }}
                value={serverId}
                onChange={onServerChange}
                options={servers.map((s) => ({
                  value: s.id,
                  label: `${s.name || s.host}${s.panel_type ? ` · ${s.panel_type}` : ""}`,
                }))}
              />
            </>
          )}

          <Divider orientation="left" plain>
            {t("services.sec_basic")}
          </Divider>
          <Space style={{ display: "flex" }} align="start" wrap>
            <Form.Item name="name" label={t("services.name")} rules={[{ required: true }]} style={{ flex: 1, minWidth: 220 }}>
              <Input maxLength={64} />
            </Form.Item>
            <Form.Item name="price" label={`${t("services.price")} (تومان)`}>
              <InputNumber min={0} style={{ width: 160 }} />
            </Form.Item>
          </Space>
          <Space wrap>
            <Form.Item name="data_gb" label={`${t("services.dataLimit")} (GB, 0=∞)`}>
              <InputNumber min={0} step={0.5} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="expire_days" label={`${t("services.duration")} (${t("services.days")}, 0=∞)`}>
              <InputNumber min={0} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="usage_reset_strategy" label={t("services.reset")}>
              <Select options={resetOpts} style={{ width: 150 }} />
            </Form.Item>
          </Space>

          <Divider orientation="left" plain>
            {t("services.sec_flags")}
          </Divider>
          <Space wrap size="large">
            <Form.Item name="purchaseable" label={t("services.f_purchaseable")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="renewable" label={t("services.f_renewable")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_test_service" label={t("services.f_test")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="one_time_only" label={t("services.f_one_time")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="resellers_only" label={t("services.f_resellers")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="users_only" label={t("services.f_users")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="create_on_hold_users" label={t("services.f_on_hold")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="append_available_data_renew" label={t("services.f_append")} valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>

          <Divider orientation="left" plain>
            {t("services.sec_button")}
          </Divider>
          <Space wrap>
            <Form.Item name="flow" label="flow">
              <Select options={flowOpts} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="button_icon" label={t("services.btn_icon")} style={{ minWidth: 220 }}>
              <Input allowClear placeholder={t("buttons.emoji_id_ph")} />
            </Form.Item>
            <Form.Item name="button_style" label={t("services.btn_style")}>
              <Select options={styleOpts} style={{ width: 150 }} />
            </Form.Item>
          </Space>

          {mode === "create" && (
            <>
              {catLoading && (
                <div style={{ marginTop: 12 }}>
                  <Spin size="small" />
                </div>
              )}
              {catalog && !catalog.ok && (
                <Alert
                  style={{ marginTop: 12 }}
                  type="warning"
                  showIcon
                  message={t(`services.prov_${catalog.error || "error"}`)}
                />
              )}
              {catalog && catalog.ok && renderProvisioning()}
            </>
          )}

          {mode === "edit" && editing?.panel_type !== "marzban" && editing?.panel_config && (
            <>
              <Divider orientation="left" plain>
                {t("services.sec_provisioning")} ({editing?.panel_type})
              </Divider>
              <pre style={{ fontSize: 11, maxHeight: 120, overflow: "auto", margin: 0 }}>
                {JSON.stringify(editing.panel_config, null, 2)}
              </pre>
            </>
          )}
        </Form>
      </Modal>
    </Card>
  );
}
