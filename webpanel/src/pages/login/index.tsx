import { useState } from "react";
import { App as AntdApp, Button, Card, Form, Input, Typography, theme } from "antd";
import { SafetyCertificateOutlined } from "@ant-design/icons";
import { useLogin } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Title, Text } = Typography;

export function LoginPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { message } = AntdApp.useApp();
  const { mutate: login, isLoading } = useLogin();
  const [step, setStep] = useState<"id" | "code">("id");
  const [identifier, setIdentifier] = useState("");
  const [sending, setSending] = useState(false);

  const requestCode = async (id: string) => {
    setSending(true);
    try {
      await api.post("/auth/request-code", { identifier: id });
    } catch {
      // ignore — the endpoint always returns ok and never reveals existence
    } finally {
      setSending(false);
    }
    setIdentifier(id);
    setStep("code");
    message.success(t("login.sent"));
  };

  const verify = (values: { code: string }) => {
    login(
      { identifier, code: values.code },
      { onError: (err: any) => message.error(err?.message || t("login.title")) },
    );
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: token.colorBgLayout,
        padding: 16,
      }}
    >
      <Card style={{ width: 384, maxWidth: "100%", boxShadow: token.boxShadowSecondary }}>
        <div style={{ textAlign: "center", marginBottom: 18 }}>
          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: 14,
              background: token.colorPrimary,
              color: "#fff",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 12px",
              fontSize: 28,
            }}
          >
            <SafetyCertificateOutlined />
          </div>
          <Title level={4} style={{ margin: 0 }}>
            {t("login.title")}
          </Title>
          <Text type="secondary">{t("login.subtitle")}</Text>
        </div>

        {step === "id" ? (
          <Form layout="vertical" onFinish={(v) => requestCode(v.identifier.trim())}>
            <Form.Item
              name="identifier"
              label={t("login.identifier")}
              rules={[{ required: true }]}
            >
              <Input
                size="large"
                placeholder={t("login.identifierPlaceholder")}
                autoComplete="off"
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={sending}>
              {t("login.sendCode")}
            </Button>
            <div style={{ marginTop: 12, textAlign: "center" }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t("login.hint")}
              </Text>
            </div>
          </Form>
        ) : (
          <Form layout="vertical" onFinish={verify}>
            <Form.Item name="code" label={t("login.code")} rules={[{ required: true }]}>
              <Input
                size="large"
                className="mono"
                placeholder={t("login.codePlaceholder")}
                maxLength={6}
                autoComplete="one-time-code"
                style={{ textAlign: "center", letterSpacing: 6, fontSize: 18 }}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={isLoading}>
              {t("login.verify")}
            </Button>
            <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between" }}>
              <Button type="link" size="small" onClick={() => setStep("id")}>
                {t("login.back")}
              </Button>
              <Button
                type="link"
                size="small"
                loading={sending}
                onClick={() => requestCode(identifier)}
              >
                {t("login.resend")}
              </Button>
            </div>
          </Form>
        )}
      </Card>
    </div>
  );
}
