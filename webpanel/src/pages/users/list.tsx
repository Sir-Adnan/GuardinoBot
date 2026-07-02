import { useState } from "react";
import { Button, Card, Input, Select, Space, Tag, Typography, theme } from "antd";
import {
  CheckCircleOutlined,
  EyeOutlined,
  RobotOutlined,
  SearchOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ROLE_COLORS, fmtDate } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { FilterBar } from "../../components/FilterBar";

const { Text } = Typography;

export function UserList() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<number | undefined>();
  const [blocked, setBlocked] = useState<string | undefined>();

  const { data, isLoading } = useList<any>({
    resource: "users",
    pagination: { current: page, pageSize },
    filters: [
      search ? { field: "search", operator: "contains", value: search } : null,
      role !== undefined ? { field: "role", operator: "eq", value: role } : null,
      blocked ? { field: "blocked", operator: "eq", value: blocked } : null,
    ].filter(Boolean) as any,
  });

  const statusTag = (r: any) =>
    r.is_blocked ? (
      <Tag icon={<StopOutlined />} color="red">{t("users.blocked")}</Tag>
    ) : r.blocked_bot ? (
      <Tag icon={<RobotOutlined />}>{t("users.blockedBot")}</Tag>
    ) : (
      <Tag icon={<CheckCircleOutlined />} color="green">{t("users.active")}</Tag>
    );

  const columns = [
    {
      title: t("users.username"),
      dataIndex: "username",
      render: (_: string, r: any) => {
        const handle = r.username ? `@${r.username}` : null;
        const primary = r.name || handle || `#${r.id}`;
        const secondary = r.name && handle ? handle : null;
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <span
              aria-hidden
              style={{
                width: 32,
                height: 32,
                flex: "none",
                display: "grid",
                placeItems: "center",
                borderRadius: 10,
                background: `${token.colorPrimary}1f`,
                color: token.colorPrimary,
                fontWeight: 700,
                fontSize: 13,
              }}
            >
              {String(r.name || r.username || "#").slice(0, 1).toUpperCase()}
            </span>
            <Space direction="vertical" size={0} style={{ minWidth: 0 }}>
              <Button
                type="link"
                size="small"
                style={{ padding: 0, height: "auto", textAlign: "start" }}
                onClick={() => navigate(`/users/show/${r.id}`)}
              >
                {primary}
              </Button>
              {secondary && (
                <Text type="secondary" style={{ fontSize: 12 }}>{secondary}</Text>
              )}
            </Space>
          </div>
        );
      },
    },
    {
      title: t("users.id"),
      dataIndex: "id",
      width: 130,
      render: (v: number) => (
        <Text className="mono" copyable={{ text: String(v) }}>{v}</Text>
      ),
    },
    {
      title: t("users.role"),
      dataIndex: "role",
      width: 130,
      render: (rl: number, r: any) => <Tag color={ROLE_COLORS[rl]}>{r.role_name}</Tag>,
    },
    {
      title: t("users.status"),
      key: "status",
      width: 150,
      render: (_: any, r: any) => statusTag(r),
    },
    {
      title: t("users.createdAt"),
      dataIndex: "created_at",
      width: 150,
      render: (v: string) => fmtDate(v),
    },
    {
      title: "",
      key: "actions",
      width: 52,
      render: (_: any, r: any) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/users/show/${r.id}`)}
        />
      ),
    },
  ];

  return (
    <Card>
      <PageHeader title={t("users.title")} subtitle={t("users.subtitle")} />
      <FilterBar>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder={t("users.search")}
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          style={{ flex: "1 1 220px", minWidth: 180 }}
        />
        <Select
          allowClear
          placeholder={t("users.role")}
          value={role}
          onChange={(v) => {
            setPage(1);
            setRole(v);
          }}
          style={{ flex: "1 1 140px", maxWidth: 220 }}
          options={[
            { value: 0, label: t("users.r_user") },
            { value: 1, label: t("users.r_reseller") },
            { value: 2, label: t("users.r_support") },
            { value: 3, label: t("users.r_admin") },
            { value: 4, label: t("users.r_super") },
          ]}
        />
        <Select
          allowClear
          placeholder={t("users.status")}
          value={blocked}
          onChange={(v) => {
            setPage(1);
            setBlocked(v);
          }}
          style={{ flex: "1 1 150px", maxWidth: 220 }}
          options={[
            { value: "active", label: t("users.active") },
            { value: "blocked", label: t("users.blocked") },
            { value: "bot", label: t("users.blockedBot") },
          ]}
        />
      </FilterBar>
      <ResponsiveTable
        size="small"
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 760 }}
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
