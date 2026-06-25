import { useState } from "react";
import { App as AntdApp, Card, Input, Space, Switch, Table, Tag } from "antd";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtNum } from "../../utils/format";

export function DiscountList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= 2;

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useList<any>({
    resource: "discounts",
    pagination: { current: page, pageSize },
    filters: search
      ? [{ field: "search", operator: "contains", value: search }]
      : [],
  });

  const toggle = async (id: number, enabled: boolean) => {
    try {
      await api.post(`/discounts/${id}/active`, { enabled });
      message.success(t("actions.done"));
      invalidate({ resource: "discounts", invalidates: ["list"] });
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
  ];

  return (
    <Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder={t("discounts.search")}
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
          style={{ width: 240 }}
        />
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 820 }}
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
