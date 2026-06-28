import { useState } from "react";
import { Button, Card, Tag } from "antd";
import { useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

const STATUS_COLORS: Record<string, string> = {
  finished: "green",
  waiting: "gold",
  rejected: "red",
  failed: "red",
  canceled: "default",
  partially_paid: "orange",
  sending: "blue",
  confirming: "blue",
};

export function TransactionList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading } = useList<any>({
    resource: "transactions",
    pagination: { current: page, pageSize },
  });

  const columns = [
    { title: t("tx.id"), dataIndex: "id", width: 80, className: "mono" },
    { title: t("tx.type"), dataIndex: "type_name" },
    {
      title: t("tx.provider"),
      dataIndex: "provider",
      render: (v: string, r: any) =>
        v ? (
          <span>
            <Tag>{v}</Tag>
            {r.provider_status && <Tag color="blue">{r.provider_status}</Tag>}
          </span>
        ) : (
          "-"
        ),
    },
    {
      title: t("tx.status"),
      dataIndex: "status_name",
      render: (v: string) => <Tag color={STATUS_COLORS[v] || "default"}>{v}</Tag>,
    },
    {
      title: t("tx.amount"),
      dataIndex: "amount",
      className: "mono",
      render: (v: number) => fmtToman(v),
    },
    {
      title: t("tx.payable"),
      dataIndex: "pay_amount",
      className: "mono",
      render: (v: number, r: any) =>
        v ? `${v} ${r.pay_currency || ""}` : "-",
    },
    {
      title: t("tx.invoice"),
      dataIndex: "invoice_url",
      render: (v: string, r: any) =>
        v ? (
          <Button type="link" size="small" href={v} target="_blank">
            {r.provider_txn_id || t("tx.invoice")}
          </Button>
        ) : (
          <span className="mono">{r.provider_txn_id || "-"}</span>
        ),
    },
    {
      title: t("tx.user"),
      dataIndex: "user_id",
      className: "mono",
      render: (v: number) => (
        <Button type="link" size="small" onClick={() => navigate(`/users/show/${v}`)}>
          {v}
        </Button>
      ),
    },
    { title: t("tx.createdAt"), dataIndex: "created_at", render: (v: string) => fmtDate(v) },
  ];

  return (
    <Card>
      <PageHeader title={t("tx.title")} subtitle={t("tx.subtitle")} />
      <ResponsiveTable
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 780 }}
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
