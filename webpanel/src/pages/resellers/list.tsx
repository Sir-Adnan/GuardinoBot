import { useState } from "react";
import { Button, Card, Input, Space, Table, Tag } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import { useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ROLE_COLORS, fmtNum, fmtToman } from "../../utils/format";

export function ResellerList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useList<any>({
    resource: "resellers",
    pagination: { current: page, pageSize },
    filters: search
      ? [{ field: "search", operator: "contains", value: search }]
      : [],
  });

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
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#ef4444" : undefined }}>{fmtToman(v)}</span>
      ),
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
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/resellers/show/${r.id}`)}
        />
      ),
    },
  ];

  return (
    <Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder={t("resellers.search")}
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
      </Space>
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
    </Card>
  );
}
