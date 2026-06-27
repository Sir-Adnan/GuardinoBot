import { useState } from "react";
import { Button, Card, Input, Tag } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import { useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ROLE_COLORS, fmtDate } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

export function UserList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useList<any>({
    resource: "users",
    pagination: { current: page, pageSize },
    filters: search
      ? [{ field: "search", operator: "contains", value: search }]
      : [],
  });

  const columns = [
    { title: t("users.id"), dataIndex: "id", width: 120, className: "mono" },
    {
      title: t("users.username"),
      dataIndex: "username",
      render: (v: string) => (v ? "@" + v : "—"),
    },
    {
      title: t("users.name"),
      dataIndex: "name",
      render: (v: string) => v || "—",
    },
    {
      title: t("users.role"),
      dataIndex: "role",
      render: (r: number, row: any) => <Tag color={ROLE_COLORS[r]}>{row.role_name}</Tag>,
    },
    {
      title: t("users.status"),
      key: "status",
      render: (_: any, row: any) =>
        row.is_blocked ? (
          <Tag color="red">{t("users.blocked")}</Tag>
        ) : row.blocked_bot ? (
          <Tag>{t("users.blockedBot")}</Tag>
        ) : (
          <Tag color="green">{t("users.active")}</Tag>
        ),
    },
    {
      title: t("users.createdAt"),
      dataIndex: "created_at",
      render: (v: string) => fmtDate(v),
    },
    {
      title: "",
      key: "actions",
      width: 56,
      render: (_: any, row: any) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/users/show/${row.id}`)}
        />
      ),
    },
  ];

  return (
    <Card>
      <PageHeader
        title={t("users.title")}
        subtitle={t("users.subtitle")}
        extra={
          <Input.Search
            placeholder={t("users.search")}
            allowClear
            onSearch={(v) => {
              setSearch(v);
              setPage(1);
            }}
            style={{ width: 240 }}
          />
        }
      />
      <ResponsiveTable
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 740 }}
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
