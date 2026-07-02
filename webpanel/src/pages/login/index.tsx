import { CSSProperties, useContext, useEffect, useState } from "react";
import { App as AntdApp, Button, Form, Input, Spin, Typography } from "antd";
import { SafetyCertificateOutlined, SendOutlined } from "@ant-design/icons";
import { useLogin } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ColorModeContext } from "../../contexts/color-mode";
import { accentColor } from "../../theme";

const { Title, Text } = Typography;

// Secondary gradient stop — indigo pairs well with every selectable accent.
const ACCENT_2 = { light: "#6366f1", dark: "#818cf8" };

/** Mode/accent-aware CSS vars consumed by the .gb-login* rules in index.css. */
function loginVars(accent: string, mode: "light" | "dark"): CSSProperties {
  const primary = accentColor(accent, mode);
  const dark = mode === "dark";
  return {
    "--gb-accent": primary,
    "--gb-accent-2": ACCENT_2[mode],
    "--gb-accent-glow": dark ? `${primary}55` : `${primary}40`,
    "--gb-bg": dark
      ? "linear-gradient(160deg, #0b0e14 0%, #10141d 55%, #0d1322 100%)"
      : "linear-gradient(160deg, #eef2f7 0%, #e7edf8 55%, #eceefb 100%)",
    "--gb-grid": dark ? "rgba(255,255,255,0.05)" : "rgba(30,41,59,0.08)",
    "--gb-card-bg": dark ? "rgba(24,28,38,0.66)" : "rgba(255,255,255,0.72)",
    "--gb-card-border": dark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)",
    "--gb-card-shadow": dark
      ? "0 24px 70px rgba(0,0,0,0.5)"
      : "0 20px 60px rgba(15,23,42,0.12)",
    "--gb-chip-bg": dark ? "rgba(255,255,255,0.05)" : "rgba(15,23,42,0.04)",
    "--gb-blob-opacity": dark ? 0.45 : 0.32,
    "--gb-title-a": dark ? "#f8fafc" : "#0f172a",
    "--gb-title-b": primary,
  } as CSSProperties;
}

function Blobs({ accent, mode }: { accent: string; mode: "light" | "dark" }) {
  const primary = accentColor(accent, mode);
  const blob = (bg: string, style: CSSProperties, delay = 0) => (
    <div
      className="gb-login-blob"
      style={{ background: bg, animationDelay: `${delay}s`, ...style }}
    />
  );
  return (
    <>
      {blob(primary, { width: "42vmax", height: "42vmax", top: "-14vmax", insetInlineStart: "-10vmax" })}
      {blob(ACCENT_2[mode], { width: "36vmax", height: "36vmax", bottom: "-12vmax", insetInlineEnd: "-8vmax" }, -6)}
      {blob("#ec4899", { width: "22vmax", height: "22vmax", bottom: "8%", insetInlineStart: "12%", opacity: 0.16 }, -11)}
    </>
  );
}

export function LoginPage() {
  const { t } = useTranslation();
  const { mode, accent } = useContext(ColorModeContext);
  const { message } = AntdApp.useApp();
  const { mutate: login, isLoading } = useLogin();
  const [step, setStep] = useState<"id" | "code">("id");
  const [identifier, setIdentifier] = useState("");
  const [sending, setSending] = useState(false);
  const [twaLoading, setTwaLoading] = useState(
    () => Boolean((window as any).Telegram?.WebApp?.initData),
  );

  // Auto-login when opened inside Telegram (signed initData → no OTP needed).
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (!tg) {
      setTwaLoading(false);
      return;
    }
    try {
      tg.ready?.();
      tg.expand?.();
    } catch {
      /* ignore */
    }
    if (!tg.initData) {
      setTwaLoading(false);
      return;
    }
    login({ init_data: tg.initData }, { onError: () => setTwaLoading(false) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const vars = loginVars(accent, mode);

  if (twaLoading) {
    return (
      <div className="gb-login" style={vars}>
        <Blobs accent={accent} mode={mode} />
        <div className="gb-login-card" style={{ display: "grid", placeItems: "center", minHeight: 160 }}>
          <Spin size="large" />
        </div>
      </div>
    );
  }

  return (
    <div className="gb-login" style={vars}>
      <Blobs accent={accent} mode={mode} />

      <div className="gb-login-card">
        <div style={{ textAlign: "center", marginBottom: 22 }}>
          <div className="gb-login-logo">
            <SafetyCertificateOutlined />
          </div>
          <Title level={3} className="gb-login-title" style={{ margin: 0, fontWeight: 800 }}>
            {t("login.title")}
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {t("login.subtitle")}
          </Text>
        </div>

        {step === "id" ? (
          <Form
            key="id"
            className="gb-login-step"
            layout="vertical"
            onFinish={(v) => requestCode(v.identifier.trim())}
          >
            <Form.Item
              name="identifier"
              label={t("login.identifier")}
              rules={[{ required: true }]}
            >
              <Input
                size="large"
                placeholder={t("login.identifierPlaceholder")}
                autoComplete="off"
                autoFocus
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={sending}
              icon={<SendOutlined />}
            >
              {t("login.sendCode")}
            </Button>
            <div style={{ marginTop: 14, textAlign: "center" }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t("login.hint")}
              </Text>
            </div>
          </Form>
        ) : (
          <Form key="code" className="gb-login-step" layout="vertical" onFinish={verify}>
            <div style={{ textAlign: "center", marginBottom: 14 }}>
              <span className="gb-login-chip">
                <SendOutlined style={{ fontSize: 12 }} />
                <span className="mono" dir="ltr">{identifier}</span>
              </span>
            </div>
            <Form.Item name="code" label={t("login.code")} rules={[{ required: true }]}>
              <Input
                size="large"
                className="mono"
                placeholder={t("login.codePlaceholder")}
                maxLength={6}
                autoComplete="one-time-code"
                inputMode="numeric"
                autoFocus
                style={{ textAlign: "center", letterSpacing: 8, fontSize: 20 }}
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
      </div>
    </div>
  );
}
