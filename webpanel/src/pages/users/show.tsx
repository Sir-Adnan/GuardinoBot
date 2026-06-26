import { useCallback, useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
} from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  DeleteOutlined,
  DollarOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useGetIdentity } from "@refinedev/core";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_COLORS, fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";

const PROXY_STATUS_COLOR: Record<string, string> = {
  active: "green",
  disabled: "default",
  limited: "orange",
  expired: "red",
  on_hold: "blue",
};

export function UserShow() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const { data: me } = useGetIdentity<any>();
  const role = me?.role ?? 0;
  const isAdmin = role >= 2;
  const isSuper = role >= 3;
  const BackIcon = i18n.language === "en" ? ArrowLeftOutlined : ArrowRightOutlined;

  const [u, setU] = useState<any | null>(null);
  const [proxies, setProxies] = useState<any[]>([]);
  const [txs, setTxs] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editForm] = Form.useForm();
  const [editOpen, setEditOpen] = useState(false);
  const [balOpen, setBalOpen] = useState(false);
  const [balForm] = Form.useForm();
  const [busy, setBusy] = useState(false);

  const loadUser = useCallback(
    () => api.get(`/users/${id}`).then((r) => setU(r.data)),
    [id],
  );

  useEffect(() => {
    Promise.all([
      loadUser(),
      api.get("/proxies", { params: { user_id: id, per_page: 100 } }).then((r) => setProxies(r.data.items ?? [])),
      api.get("/transactions", { params: { user_id: id, per_page: 100 } }).then((r) => setTxs(r.data.items ?? [])).catch(() => undefined),
      isSuper
        ? api.get("/audit", { params: { target_type: "user", target_id: id, per_page: 100 } }).then((r) => setLogs(r.data.items ?? [])).catch(() => undefined)
        : Promise.resolve(),
    ])
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading || !u) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 300 }}>
        <Spin />
      </div>
    );
  }

  const setBlocked = async (blocked: boolean) => {
    try {
      await api.post(`/users/${id}/block`, { blocked });
      message.success(t("actions.done"));
      loadUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const openEdit = () => {
    editForm.setFieldsValue({
      role: u.role,
      is_postpaid: u.is_postpaid,
      max_post_paid_credit: u.max_post_paid_credit,
      daily_test_services: u.daily_test_services,
      discount_percentage: u.discount_percentage,
      proxy_username_prefix: u.proxy_username_prefix ?? "",
    });
    setEditOpen(true);
  };

  const saveEdit = async (v: any) => {
    setBusy(true);
    try {
      const payload: any = {
        is_postpaid: !!v.is_postpaid,
        max_post_paid_credit: v.max_post_paid_credit,
        daily_test_services: v.daily_test_services,
        discount_percentage: v.discount_percentage,
        proxy_username_prefix: v.proxy_username_prefix || "",
      };
      if (isSuper) payload.role = v.role;
      await api.patch(`/users/${id}`, payload);
      message.success(t("users.saved"));
      setEditOpen(false);
      loadUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const saveBalance = async (v: any) => {
    setBusy(true);
    try {
      await api.post(`/users/${id}/balance`, {
        amount: v.amount,
        direction: v.direction,
      });
      message.success(t("actions.done"));
      setBalOpen(false);
      balForm.resetFields();
      loadUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const proxyAction = async (pid: number, action: string) => {
    try {
      await api.post(`/proxies/${pid}/action`, { action });
      message.success(t("actions.done"));
      const r = await api.get("/proxies", { params: { user_id: id, per_page: 100 } });
      setProxies(r.data.items ?? []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const proxyDelete = async (pid: number) => {
    try {
      await api.delete(`/proxies/${pid}`);
      message.success(t("actions.deleted"));
      setProxies((p) => p.filter((x) => x.id !== pid));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const overview = (
    <>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 1, md: 2 }}>
        <Descriptions.Item label={t("users.id")}>
          <span className="mono">{u.id}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.username")}>
          {u.username ? "@" + u.username : "—"}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.name")}>{u.name || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("users.role")}>
          <Tag color={ROLE_COLORS[u.role]}>{u.role_name}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.balance")}>
          <span className="mono">{fmtToman(u.balance)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.proxies")}>
          <span className="mono">{u.proxies_count}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.postpaid")}>
          {u.is_postpaid ? `${t("common.yes")} (${fmtToman(u.max_post_paid_credit)})` : t("common.no")}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.discountPct")}>
          <span className="mono">{u.discount_percentage}%</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.testCount")}>
          <span className="mono">{u.daily_test_services}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.prefix")}>{u.proxy_username_prefix || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("users.verified")}>
          {u.is_verified ? t("common.yes") : t("common.no")}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.createdAt")}>{fmtDate(u.created_at)}</Descriptions.Item>
      </Descriptions>
      {isAdmin && (
        <Space style={{ marginTop: 16 }} wrap>
          {u.is_blocked ? (
            <Button onClick={() => setBlocked(false)}>{t("actions.unblock")}</Button>
          ) : (
            <Popconfirm title={t("actions.blockConfirm")} okButtonProps={{ danger: true }} onConfirm={() => setBlocked(true)}>
              <Button danger>{t("actions.block")}</Button>
            </Popconfirm>
          )}
          <Button icon={<EditOutlined />} onClick={openEdit}>
            {t("users.edit")}
          </Button>
          {isSuper && (
            <Button icon={<DollarOutlined />} onClick={() => setBalOpen(true)}>
              {t("users.balanceAdjust")}
            </Button>
          )}
        </Space>
      )}
    </>
  );

  const subsCols = [
    { title: t("users.id"), dataIndex: "id", width: 64, className: "mono" },
    { title: t("users.username"), dataIndex: "username", className: "mono" },
    { title: t("users.service"), dataIndex: "service_name", render: (v: string, r: any) => r.custom_name || v || "—" },
    { title: t("users.server"), dataIndex: "server_name", render: (v: string) => v || "—" },
    {
      title: t("users.status"),
      dataIndex: "status",
      render: (v: string) => <Tag color={PROXY_STATUS_COLOR[v] || "default"}>{v}</Tag>,
    },
    {
      title: t("services.actions"),
      key: "act",
      render: (_: any, r: any) =>
        isAdmin ? (
          <Space size={2} wrap>
            <Button size="small" onClick={() => proxyAction(r.id, "enable")}>{t("users.enable")}</Button>
            <Button size="small" onClick={() => proxyAction(r.id, "disable")}>{t("users.disable")}</Button>
            <Popconfirm title={t("users.resetConfirm")} onConfirm={() => proxyAction(r.id, "reset_usage")}>
              <Button size="small">{t("users.reset")}</Button>
            </Popconfirm>
            <Popconfirm title={t("users.revokeConfirm")} onConfirm={() => proxyAction(r.id, "revoke")}>
              <Button size="small">{t("users.revoke")}</Button>
            </Popconfirm>
            <Popconfirm title={t("users.deleteConfirm")} okButtonProps={{ danger: true }} onConfirm={() => proxyDelete(r.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        ) : null,
    },
  ];

  const txCols = [
    { title: t("users.id"), dataIndex: "id", width: 64, className: "mono" },
    { title: t("users.type"), dataIndex: "type_name" },
    { title: t("users.amount"), dataIndex: "amount", className: "mono", render: (v: number) => fmtToman(v) },
    { title: t("users.status"), dataIndex: "status_name" },
    { title: t("users.createdAt"), dataIndex: "created_at", render: (v: string) => fmtDate(v) },
  ];

  const logCols = [
    { title: t("users.createdAt"), dataIndex: "created_at", render: (v: string) => fmtDate(v) },
    { title: t("audit.action"), dataIndex: "action" },
    { title: t("audit.source"), dataIndex: "source" },
    { title: t("audit.actor"), dataIndex: "actor_name", render: (v: string) => v || "—" },
    { title: t("audit.amount"), dataIndex: "amount", render: (v: number) => (v != null ? fmtToman(v) : "—") },
  ];

  const tabs = [
    { key: "overview", label: t("users.tab_overview"), children: overview },
    {
      key: "subs",
      label: `${t("users.tab_subs")} (${proxies.length})`,
      children: <Table rowKey="id" size="small" dataSource={proxies} columns={subsCols} scroll={{ x: 720 }} pagination={false} />,
    },
    {
      key: "payments",
      label: `${t("users.tab_payments")} (${txs.length})`,
      children: <Table rowKey="id" size="small" dataSource={txs} columns={txCols} scroll={{ x: 560 }} pagination={false} />,
    },
    ...(isSuper
      ? [{
          key: "logs",
          label: `${t("users.tab_logs")} (${logs.length})`,
          children: <Table rowKey="id" size="small" dataSource={logs} columns={logCols} scroll={{ x: 560 }} pagination={false} />,
        }]
      : []),
  ];

  return (
    <Card>
      <PageHeader
        icon={<Button type="text" icon={<BackIcon />} onClick={() => navigate("/users")} />}
        title={u.name || (u.username ? "@" + u.username : `#${u.id}`)}
        subtitle={<span className="mono">#{u.id}{u.username ? ` · @${u.username}` : ""}</span>}
      />
      <Tabs items={tabs} />

      <Modal open={editOpen} title={t("users.editTitle")} onCancel={() => setEditOpen(false)} onOk={() => editForm.submit()} confirmLoading={busy} okText={t("buttons.save")} destroyOnClose>
        <Form form={editForm} layout="vertical" onFinish={saveEdit} preserve={false}>
          {isSuper && (
            <Form.Item name="role" label={t("users.role")}>
              <Select
                options={[0, 1, 2, 3].map((n) => ({ value: n, label: t(`roles.${n}`) }))}
              />
            </Form.Item>
          )}
          <Space wrap>
            <Form.Item name="is_postpaid" label={t("users.postpaid")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="max_post_paid_credit" label={t("users.maxCredit")}>
              <InputNumber min={0} style={{ width: 160 }} />
            </Form.Item>
          </Space>
          <Space wrap>
            <Form.Item name="daily_test_services" label={t("users.testCount")}>
              <InputNumber min={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="discount_percentage" label={t("users.discountPct")}>
              <InputNumber min={0} max={100} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="proxy_username_prefix" label={t("users.prefix")}>
              <Input maxLength={25} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal open={balOpen} title={t("users.balanceAdjust")} onCancel={() => setBalOpen(false)} onOk={() => balForm.submit()} confirmLoading={busy} okText={t("buttons.save")} destroyOnClose>
        <Form form={balForm} layout="vertical" onFinish={saveBalance} initialValues={{ direction: "charge" }}>
          <Form.Item name="direction">
            <Segmented
              options={[
                { value: "charge", label: t("users.charge") },
                { value: "decharge", label: t("users.decharge") },
              ]}
              block
            />
          </Form.Item>
          <Form.Item name="amount" label={`${t("users.amount")} (تومان)`} rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
