import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
} from "antd";
import { EyeOutlined, UserAddOutlined } from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_COLORS, fmtNum, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";

export function ResellerList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isSuper = (me?.role ?? 0) >= 3;
  const [form] = Form.useForm();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const { data, isLoading } = useList<any>({
    resource: "resellers",
    pagination: { current: page, pageSize },
    filters: search ? [{ field: "search", operator: "contains", value: search }] : [],
  });

  const promote = async (v: any) => {
    setBusy(true);
    try {
      await api.post("/resellers/promote", { identifier: v.identifier });
      message.success(t("resellers.promoted"));
      setPromoteOpen(false);
      form.resetFields();
      invalidate({ resource: "resellers", invalidates: ["list"] });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { title: t("resellers.id"), dataIndex: "id", width: 110, className: "mono" },
    {
      title: t("resellers.name"),
      key: "name",
      render: (_: any, r: any) => r.name || (r.username ? "@" + r.username : "—"),
    },
    {
      title: t("resellers.role"),
      dataIndex: "role",
      render: (v: number, r: any) => <Tag color={ROLE_COLORS[v]}>{r.role_name}</Tag>,
    },
    {
      title: t("resellers.balance"),
      dataIndex: "balance",
      className: "mono",
      render: (v: number) => <span style={{ color: v < 0 ? "#ef4444" : undefined }}>{fmtToman(v)}</span>,
    },
    {
      title: t("resellers.children"),
      dataIndex: "children_count",
      className: "mono",
      render: (v: number) => fmtNum(v),
    },
    {
      title: t("resellers.postpaid"),
      dataIndex: "is_postpaid",
      render: (v: boolean) => (v ? <Tag color="purple">{t("common.yes")}</Tag> : "—"),
    },
    {
      title: t("resellers.status"),
      dataIndex: "is_blocked",
      render: (v: boolean) =>
        v ? <Tag color="red">{t("users.blocked")}</Tag> : <Tag color="green">{t("users.active")}</Tag>,
    },
    {
      title: "",
      key: "actions",
      width: 56,
      render: (_: any, r: any) => (
        <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/resellers/show/${r.id}`)} />
      ),
    },
  ];

  return (
    <Card>
      <PageHeader
        title={t("resellers.title")}
        subtitle={t("resellers.subtitle")}
        extra={
          <Space wrap>
            <Input.Search
              placeholder={t("resellers.search")}
              allowClear
              onSearch={(v) => {
                setSearch(v);
                setPage(1);
              }}
              style={{ width: 220 }}
            />
            {isSuper && (
              <Button type="primary" icon={<UserAddOutlined />} onClick={() => setPromoteOpen(true)}>
                {t("resellers.promote")}
              </Button>
            )}
          </Space>
        }
      />
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 860 }}
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
        open={promoteOpen}
        title={t("resellers.promoteTitle")}
        onCancel={() => setPromoteOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={busy}
        okText={t("resellers.promote")}
        destroyOnClose
      >
        <p style={{ color: "#888" }}>{t("resellers.promoteHint")}</p>
        <Form form={form} layout="vertical" onFinish={promote}>
          <Form.Item name="identifier" label={t("resellers.identifier")} rules={[{ required: true }]}>
            <Input placeholder="123456789  /  @username" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
