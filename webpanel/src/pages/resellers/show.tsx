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
  Segmented,
  Select,
  Skeleton,
  Space,
  Switch,
  Tabs,
  Tag,
} from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CreditCardOutlined,
  DollarOutlined,
  EditOutlined,
  EyeOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { theme } from "antd";
import { useGetIdentity } from "@refinedev/core";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_COLORS, ROLE_SUPER, ROLE_VALUES, fmtDate, fmtNum, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { StatCard } from "../../components/StatCard";

export function ResellerShow() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const { data: me } = useGetIdentity<any>();
  const isSuper = (me?.role ?? 0) >= ROLE_SUPER;
  const BackIcon = i18n.language === "en" ? ArrowLeftOutlined : ArrowRightOutlined;

  const [r, setR] = useState<any | null>(null);
  const [u, setU] = useState<any | null>(null);
  const [children, setChildren] = useState<any[]>([]);
  const [proxies, setProxies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editForm] = Form.useForm();
  const [editOpen, setEditOpen] = useState(false);
  const [balForm] = Form.useForm();
  const [balOpen, setBalOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadCore = useCallback(
    () =>
      Promise.all([
        api.get(`/resellers/${id}`).then((x) => setR(x.data)),
        api.get(`/users/${id}`).then((x) => setU(x.data)),
      ]),
    [id],
  );

  useEffect(() => {
    Promise.all([
      loadCore(),
      api.get(`/resellers/${id}/children`, { params: { per_page: 200 } }).then((x) => setChildren(x.data.items ?? [])).catch(() => undefined),
      api.get("/proxies", { params: { user_id: id, per_page: 100 } }).then((x) => setProxies(x.data.items ?? [])).catch(() => undefined),
    ])
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading || !r || !u) {
    return (
      <Card>
        <Skeleton active avatar paragraph={{ rows: 1 }} />
        <Skeleton active paragraph={{ rows: 6 }} style={{ marginTop: 24 }} />
      </Card>
    );
  }

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
      loadCore();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const saveBalance = async (v: any) => {
    setBusy(true);
    try {
      await api.post(`/users/${id}/balance`, { amount: v.amount, direction: v.direction });
      message.success(t("actions.done"));
      setBalOpen(false);
      balForm.resetFields();
      loadCore();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const overview = (
    <>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 1, md: 2 }}>
        <Descriptions.Item label={t("resellers.id")}><span className="mono">{r.id}</span></Descriptions.Item>
        <Descriptions.Item label={t("resellers.username")}>{r.username ? "@" + r.username : "—"}</Descriptions.Item>
        <Descriptions.Item label={t("resellers.role")}><Tag color={ROLE_COLORS[r.role]}>{r.role_name}</Tag></Descriptions.Item>
        <Descriptions.Item label={t("resellers.balance")}>
          <span className="mono" style={{ color: r.balance < 0 ? "#ef4444" : undefined }}>{fmtToman(r.balance)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.availableCredit")}><span className="mono">{fmtToman(r.available_credit)}</span></Descriptions.Item>
        <Descriptions.Item label={t("resellers.postpaid")}>
          {r.is_postpaid ? `${t("common.yes")} (${fmtToman(r.max_post_paid_credit)})` : t("common.no")}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.discountPct")}><span className="mono">{u.discount_percentage}%</span></Descriptions.Item>
        <Descriptions.Item label={t("resellers.children")}><span className="mono">{fmtNum(r.children_count)}</span></Descriptions.Item>
        <Descriptions.Item label={t("resellers.proxies")}><span className="mono">{fmtNum(r.proxies_count)}</span></Descriptions.Item>
        <Descriptions.Item label={t("resellers.createdAt")}>{fmtDate(r.created_at)}</Descriptions.Item>
      </Descriptions>
    </>
  );

  const headerActions = isSuper ? (
    <Space wrap>
      <Button icon={<EditOutlined />} onClick={openEdit}>{t("users.edit")}</Button>
      <Button type="primary" ghost icon={<DollarOutlined />} onClick={() => setBalOpen(true)}>
        {t("users.balanceAdjust")}
      </Button>
    </Space>
  ) : undefined;

  const childCols = [
    { title: t("users.id"), dataIndex: "id", width: 110, className: "mono" },
    { title: t("users.username"), dataIndex: "username", render: (v: string) => (v ? "@" + v : "—") },
    { title: t("users.name"), dataIndex: "name", render: (v: string) => v || "—" },
    { title: t("users.role"), dataIndex: "role", render: (v: number, row: any) => <Tag color={ROLE_COLORS[v]}>{row.role_name}</Tag> },
    {
      title: "",
      key: "act",
      width: 50,
      render: (_: any, row: any) => (
        <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/users/show/${row.id}`)} />
      ),
    },
  ];

  const proxyCols = [
    { title: t("users.id"), dataIndex: "id", width: 64, className: "mono" },
    { title: t("users.username"), dataIndex: "username", className: "mono" },
    { title: t("users.service"), dataIndex: "service_name", render: (v: string, x: any) => x.custom_name || v || "—" },
    { title: t("users.status"), dataIndex: "status", render: (v: string) => <Tag>{v}</Tag> },
  ];

  const tabs = [
    { key: "overview", label: t("users.tab_overview"), children: overview },
    {
      key: "children",
      label: `${t("resellers.children")} (${children.length})`,
      children: <ResponsiveTable rowKey="id" size="small" dataSource={children} columns={childCols} scroll={{ x: 560 }} pagination={false} />,
    },
    {
      key: "subs",
      label: `${t("users.tab_subs")} (${proxies.length})`,
      children: <ResponsiveTable rowKey="id" size="small" dataSource={proxies} columns={proxyCols} scroll={{ x: 520 }} pagination={false} />,
    },
  ];

  return (
    <Card>
      <PageHeader
        icon={
          <Space size={10}>
            <Button type="text" icon={<BackIcon />} onClick={() => navigate("/resellers")} />
            <span
              aria-hidden
              style={{
                width: 46,
                height: 46,
                display: "grid",
                placeItems: "center",
                borderRadius: 14,
                background: `${token.colorPrimary}1f`,
                color: token.colorPrimary,
                fontWeight: 800,
                fontSize: 19,
              }}
            >
              {String(r.name || r.username || "#").slice(0, 1).toUpperCase()}
            </span>
          </Space>
        }
        title={
          <Space size={8} wrap>
            {r.name || (r.username ? "@" + r.username : `#${r.id}`)}
            <Tag color={ROLE_COLORS[r.role]} style={{ margin: 0 }}>{r.role_name}</Tag>
            {r.is_blocked && <Tag color="red" style={{ margin: 0 }}>{t("users.blocked")}</Tag>}
          </Space>
        }
        subtitle={<span className="mono">#{r.id}{r.username ? ` · @${r.username}` : ""}</span>}
        extra={headerActions}
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <StatCard label={t("resellers.balance")} value={fmtToman(r.balance)} icon={<WalletOutlined />} />
        <StatCard
          label={t("resellers.availableCredit")}
          value={fmtToman(r.available_credit)}
          icon={<CreditCardOutlined />}
        />
        <StatCard label={t("resellers.children")} value={fmtNum(r.children_count)} icon={<TeamOutlined />} />
        <StatCard label={t("resellers.proxies")} value={fmtNum(r.proxies_count)} icon={<ThunderboltOutlined />} />
      </div>
      <Tabs items={tabs} />

      <Modal open={editOpen} title={t("users.editTitle")} onCancel={() => setEditOpen(false)} onOk={() => editForm.submit()} confirmLoading={busy} okText={t("buttons.save")} destroyOnClose>
        <Form form={editForm} layout="vertical" onFinish={saveEdit} preserve={false}>
          {isSuper && (
            <Form.Item name="role" label={t("users.role")}>
              <Select options={ROLE_VALUES.map((n) => ({ value: n, label: t(`roles.${n}`) }))} />
            </Form.Item>
          )}
          <Space wrap>
            <Form.Item name="is_postpaid" label={t("users.postpaid")} valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="max_post_paid_credit" label={t("users.maxCredit")}><InputNumber min={0} style={{ width: 160 }} /></Form.Item>
          </Space>
          <Space wrap>
            <Form.Item name="daily_test_services" label={t("users.testCount")}><InputNumber min={0} style={{ width: 120 }} /></Form.Item>
            <Form.Item name="discount_percentage" label={t("users.discountPct")}><InputNumber min={0} max={100} style={{ width: 120 }} /></Form.Item>
            <Form.Item name="proxy_username_prefix" label={t("users.prefix")}><Input maxLength={25} /></Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal open={balOpen} title={t("users.balanceAdjust")} onCancel={() => setBalOpen(false)} onOk={() => balForm.submit()} confirmLoading={busy} okText={t("buttons.save")} destroyOnClose>
        <Form form={balForm} layout="vertical" onFinish={saveBalance} initialValues={{ direction: "charge" }}>
          <Form.Item name="direction">
            <Segmented options={[{ value: "charge", label: t("users.charge") }, { value: "decharge", label: t("users.decharge") }]} block />
          </Form.Item>
          <Form.Item name="amount" label={`${t("users.amount")} (تومان)`} rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
