import { Button, Card, Descriptions, Space, Spin, Tag } from "antd";
import { ArrowLeftOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useOne } from "@refinedev/core";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ROLE_COLORS, fmtDate, fmtNum, fmtToman } from "../../utils/format";

export function ResellerShow() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, isLoading } = useOne<any>({ resource: "resellers", id: id! });
  const u = data?.data;

  if (isLoading || !u) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 300 }}>
        <Spin />
      </div>
    );
  }

  const BackIcon = i18n.language === "en" ? ArrowLeftOutlined : ArrowRightOutlined;

  return (
    <Card
      title={
        <Space>
          <Button type="text" icon={<BackIcon />} onClick={() => navigate("/resellers")} />
          {u.name || (u.username ? "@" + u.username : u.id)}
        </Space>
      }
    >
      <Descriptions bordered size="middle" column={{ xs: 1, sm: 1, md: 2 }}>
        <Descriptions.Item label={t("resellers.id")}>
          <span className="mono">{u.id}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.username")}>
          {u.username ? "@" + u.username : "—"}
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.role")}>
          <Tag color={ROLE_COLORS[u.role]}>{u.role_name}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.balance")}>
          <span className="mono" style={{ color: u.balance < 0 ? "#ef4444" : undefined }}>
            {fmtToman(u.balance)}
          </span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.availableCredit")}>
          <span className="mono">{fmtToman(u.available_credit)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.postpaid")}>
          {u.is_postpaid
            ? `${t("common.yes")} (${fmtToman(u.max_post_paid_credit)})`
            : t("common.no")}
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.children")}>
          <span className="mono">{fmtNum(u.children_count)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.proxies")}>
          <span className="mono">{fmtNum(u.proxies_count)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.status")}>
          {u.is_blocked ? (
            <Tag color="red">{t("users.blocked")}</Tag>
          ) : (
            <Tag color="green">{t("users.active")}</Tag>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t("resellers.createdAt")}>
          {fmtDate(u.created_at)}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
