import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Tag,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtNum } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

export function DiscountList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= 2;
  const [form] = Form.useForm();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);

  const { data, isLoading } = useList<any>({
    resource: "discounts",
    pagination: { current: page, pageSize },
    filters: search ? [{ field: "search", operator: "contains", value: search }] : [],
  });

  const refresh = () => invalidate({ resource: "discounts", invalidates: ["list"] });

  const toggle = async (id: number, enabled: boolean) => {
    try {
      await api.post(`/discounts/${id}/active`, { enabled });
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      percentage: 10,
      on_purchase: true,
      on_renew: false,
      once_per_user: false,
      is_active: true,
    });
    setOpen(true);
  };

  const openEdit = (r: any) => {
    setEditing(r);
    form.resetFields();
    form.setFieldsValue({
      code: r.code ?? "",
      percentage: r.percentage,
      on_purchase: r.on_purchase,
      on_renew: r.on_renew,
      once_per_user: r.once_per_user,
      use_counts: r.use_counts ?? undefined,
      expires_at: r.expires_at ? dayjs(r.expires_at) : null,
      is_active: r.is_active,
    });
    setOpen(true);
  };

  const submit = async (v: any) => {
    setSaving(true);
    const payload = {
      code: v.code || null,
      percentage: v.percentage,
      on_purchase: !!v.on_purchase,
      on_renew: !!v.on_renew,
      once_per_user: !!v.once_per_user,
      use_counts: v.use_counts ?? null,
      expires_at: v.expires_at ? v.expires_at.toISOString() : null,
      is_active: !!v.is_active,
    };
    try {
      if (editing) await api.patch(`/discounts/${editing.id}`, payload);
      else await api.post("/discounts", payload);
      message.success(t(editing ? "discounts.saved" : "discounts.created"));
      setOpen(false);
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.delete(`/discounts/${id}`);
      message.success(t("actions.deleted"));
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const columns = [
    {
      title: t("discounts.code"),
      dataIndex: "code",
      className: "mono",
      render: (v: string) => (v ? <Tag>{v}</Tag> : "—"),
    },
    {
      title: t("discounts.percentage"),
      dataIndex: "percentage",
      className: "mono",
      render: (v: number) => `${v}%`,
    },
    {
      title: t("discounts.active"),
      dataIndex: "is_active",
      render: (v: boolean, r: any) =>
        isAdmin ? (
          <Switch checked={v} onChange={(c) => toggle(r.id, c)} />
        ) : v ? (
          <Tag color="green">{t("common.yes")}</Tag>
        ) : (
          <Tag>{t("common.no")}</Tag>
        ),
    },
    {
      title: t("discounts.applies"),
      key: "applies",
      render: (_: any, r: any) => (
        <Space size={4} wrap>
          {r.on_purchase && <Tag color="blue">{t("discounts.onPurchase")}</Tag>}
          {r.on_renew && <Tag color="cyan">{t("discounts.onRenew")}</Tag>}
          {r.once_per_user && <Tag color="gold">{t("discounts.oncePerUser")}</Tag>}
        </Space>
      ),
    },
    {
      title: t("discounts.usage"),
      key: "usage",
      className: "mono",
      render: (_: any, r: any) =>
        `${fmtNum(r.used_times)} / ${r.use_counts == null ? "∞" : fmtNum(r.use_counts)}`,
    },
    {
      title: t("discounts.expiresAt"),
      dataIndex: "expires_at",
      render: (v: string) => (v ? fmtDate(v) : "—"),
    },
    ...(isAdmin
      ? [
          {
            title: t("services.actions"),
            key: "actions",
            width: 100,
            render: (_: any, r: any) => (
              <Space size={2}>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
                <Popconfirm
                  title={t("discounts.deleteConfirm")}
                  okButtonProps={{ danger: true }}
                  onConfirm={() => remove(r.id)}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <Card>
      <PageHeader
        title={t("discounts.title")}
        subtitle={t("discounts.subtitle")}
        extra={
          <Space wrap>
            <Input.Search
              placeholder={t("discounts.search")}
              allowClear
              onSearch={(v) => {
                setSearch(v);
                setPage(1);
              }}
              style={{ width: 220 }}
            />
            {isAdmin && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
                {t("discounts.new")}
              </Button>
            )}
          </Space>
        }
      />
      <ResponsiveTable
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 900 }}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          showSizeChanger: true,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      <Modal
        open={open}
        title={editing ? t("discounts.editTitle") : t("discounts.addTitle")}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText={t("buttons.save")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={submit} preserve={false}>
          <Space wrap>
            <Form.Item name="code" label={t("discounts.code")} tooltip={t("discounts.codeHint")}>
              <Input maxLength={32} placeholder={t("discounts.codeAuto")} />
            </Form.Item>
            <Form.Item name="percentage" label={t("discounts.percentage")} rules={[{ required: true }]}>
              <InputNumber min={0} max={100} addonAfter="%" />
            </Form.Item>
            <Form.Item name="use_counts" label={t("discounts.maxUses")} tooltip={t("discounts.unlimited")}>
              <InputNumber min={1} placeholder="∞" />
            </Form.Item>
          </Space>
          <Form.Item name="expires_at" label={t("discounts.expiresAt")}>
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Space wrap size="large">
            <Form.Item name="on_purchase" label={t("discounts.onPurchase")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="on_renew" label={t("discounts.onRenew")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="once_per_user" label={t("discounts.oncePerUser")} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_active" label={t("discounts.active")} valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  );
}
