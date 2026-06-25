import { Card, Space, Table, Tag } from "antd";
import { useList } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtToman } from "../../utils/format";

const gb = (b: number) =>
  b ? `${(b / 1073741824).toFixed(b % 1073741824 ? 1 : 0)} GB` : "∞";

export function ServiceList() {
  const { t } = useTranslation();
  const { data, isLoading } = useList<any>({
    resource: "services",
    pagination: { current: 1, pageSize: 100 },
  });

  const columns = [
    { title: t("services.id"), dataIndex: "id", width: 70, className: "mono" },
    { title: t("services.name"), dataIndex: "name" },
    {
      title: t("services.server"),
      dataIndex: "server_name",
      render: (v: string) => v || "—",
    },
    {
      title: t("services.dataLimit"),
      dataIndex: "data_limit",
      className: "mono",
      render: (v: number) => gb(v),
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
      render: (v: number) => fmtToman(v),
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
  ];

  return (
    <Card>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 820 }}
        pagination={false}
      />
    </Card>
  );
}
