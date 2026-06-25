import { App as AntdApp, Button, Card, Descriptions, Popconfirm, Space, Spin, Tag } from "antd";
import { ArrowLeftOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useOne } from "@refinedev/core";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_COLORS, fmtDate, fmtToman } from "../../utils/format";

export function UserShow() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= 2;
  const { data, isLoading } = useOne<any>({ resource: "users", id: id! });
  const u = data?.data;

  if (isLoading || !u) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 300 }}>
        <Spin />
      </div>
    );
  }

  const BackIcon = i18n.language === "en" ? ArrowLeftOutlined : ArrowRightOutlined;

  const setBlocked = async (blocked: boolean) => {
    try {
      await api.post(`/users/${id}/block`, { blocked });
      message.success(t("actions.done"));
      invalidate({ resource: "users", invalidates: ["detail"], id: id! });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  return (
    <Card
      title={
        <Space>
          <Button type="text" icon={<BackIcon />} onClick={() => navigate("/users")} />
          {u.name || (u.username ? "@" + u.username : u.id)}
        </Space>
      }
      extra={
        isAdmin ? (
          u.is_blocked ? (
            <Button onClick={() => setBlocked(false)}>{t("actions.unblock")}</Button>
          ) : (
            <Popconfirm
              title={t("actions.blockConfirm")}
              okButtonProps={{ danger: true }}
              onConfirm={() => setBlocked(true)}
            >
              <Button danger>{t("actions.block")}</Button>
            </Popconfirm>
          )
        ) : null
      }
    >
      <Descriptions bordered size="middle" column={{ xs: 1, sm: 1, md: 2 }}>
        <Descriptions.Item label={t("users.id")}>
          <span className="mono">{u.id}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.username")}>
          {u.username ? "@" + u.username : "—"}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.name")}>{u.name || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("users.role")}>
          <Tag color={ROLE_COLORS[u.role]}>{u.role_name}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.balance")}>
          <span className="mono">{fmtToman(u.balance)}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.proxies")}>
          <span className="mono">{u.proxies_count}</span>
        </Descriptions.Item>
        <Descriptions.Item label={t("users.status")}>
          {u.is_blocked ? (
            <Tag color="red">{t("users.blocked")}</Tag>
          ) : (
            <Tag color="green">{t("users.active")}</Tag>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.verified")}>
          {u.is_verified ? t("common.yes") : t("common.no")}
        </Descriptions.Item>
        <Descriptions.Item label={t("users.createdAt")}>
          {fmtDate(u.created_at)}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
