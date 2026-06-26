import { useContext, useState, type ReactNode } from "react";
import {
  Avatar,
  Button,
  Drawer,
  Dropdown,
  Grid,
  Input,
  Layout,
  Menu,
  Tooltip,
  Typography,
  theme,
} from "antd";
import {
  ApartmentOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  BgColorsOutlined,
  BulbOutlined,
  CalendarOutlined,
  CloudServerOutlined,
  ClusterOutlined,
  CreditCardOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FontSizeOutlined,
  LayoutOutlined,
  LogoutOutlined,
  MenuOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SendOutlined,
  SettingOutlined,
  ShopOutlined,
  TagsOutlined,
  TeamOutlined,
  TranslationOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useGetIdentity, useLogout } from "@refinedev/core";

import { ColorModeContext } from "../contexts/color-mode";
import { ACCENT_KEYS, accentColor, FONT_KEYS, FONTS } from "../theme";

const FONT_LABELS: Record<string, string> = {
  vazirmatn: "Vazirmatn",
  vazir: "Vazir",
  sahel: "Sahel",
  samim: "Samim",
  system: "System",
};

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;
const { Text } = Typography;

const SIDER_WIDTH = 264;

interface Identity {
  name?: string;
  username?: string;
  role_name?: string;
  role?: number;
}

const TITLE_KEYS: Record<string, string> = {
  "/": "dashboard.title",
  "/users": "users.title",
  "/proxies": "proxies.title",
  "/services": "services.title",
  "/menus": "menus.title",
  "/transactions": "tx.title",
  "/servers": "servers.title",
  "/reports": "reports.title",
  "/resellers": "resellers.title",
  "/discounts": "discounts.title",
  "/automation": "automation.title",
  "/audit": "audit.title",
  "/texts": "texts.title",
  "/buttons": "buttons.title",
  "/settings": "settings.title",
};

export function AppLayout({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const { mode, toggle, accent, setAccent, calendar, setCalendar, font, setFont } =
    useContext(ColorModeContext);
  const { token } = theme.useToken();
  const screens = useBreakpoint();
  const navigate = useNavigate();
  const location = useLocation();
  const { mutate: logout } = useLogout();
  const { data: identity } = useGetIdentity<Identity>();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isMobile = !screens.lg;
  const isRtl = i18n.language !== "en";

  const selectedKey =
    location.pathname === "/" ? "/" : "/" + location.pathname.split("/")[1];

  // Services + Panels are admin+ (backend require_role(admin)); hide them from
  // resellers so they don't hit 403s.
  const isAdmin = (identity?.role ?? 0) >= 2;
  const isSuper = (identity?.role ?? 0) >= 3;
  const menuItems = [
    {
      type: "group" as const,
      label: t("nav.sales"),
      children: [
        { key: "/", icon: <DashboardOutlined />, label: t("nav.dashboard") },
        { key: "/users", icon: <TeamOutlined />, label: t("nav.users") },
        { key: "/proxies", icon: <ClusterOutlined />, label: t("nav.proxies") },
        ...(isAdmin
          ? [
              { key: "/services", icon: <AppstoreOutlined />, label: t("nav.services") },
              { key: "/discounts", icon: <TagsOutlined />, label: t("nav.discounts") },
            ]
          : []),
        ...(isSuper
          ? [{ key: "/menus", icon: <ApartmentOutlined />, label: t("nav.menus") }]
          : []),
        { key: "/transactions", icon: <CreditCardOutlined />, label: t("nav.transactions") },
        ...(isAdmin
          ? [{ key: "/reports", icon: <BarChartOutlined />, label: t("nav.reports") }]
          : []),
      ],
    },
    ...(isAdmin
      ? [
          {
            type: "group" as const,
            label: t("nav.system"),
            children: [
              { key: "/resellers", icon: <ShopOutlined />, label: t("nav.resellers") },
              { key: "/servers", icon: <CloudServerOutlined />, label: t("nav.servers") },
              { key: "/automation", icon: <SendOutlined />, label: t("nav.automation") },
              ...(isSuper
                ? [
                    { key: "/audit", icon: <AuditOutlined />, label: t("nav.audit") },
                    { key: "/texts", icon: <FileTextOutlined />, label: t("nav.texts") },
                    { key: "/buttons", icon: <LayoutOutlined />, label: t("nav.buttons") },
                    { key: "/settings", icon: <SettingOutlined />, label: t("nav.settings") },
                  ]
                : []),
            ],
          },
        ]
      : []),
  ];

  const go = (key: string) => {
    navigate(key);
    setDrawerOpen(false);
  };

  const toggleLang = () => {
    const next = i18n.language === "fa" ? "en" : "fa";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  };

  const initial = (identity?.name || identity?.username || "؟").trim().slice(0, 1);

  const sideContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 11,
          padding: "18px 18px 14px",
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 11,
            background: token.colorPrimary,
            color: "#fff",
            display: "grid",
            placeItems: "center",
            flex: "none",
            fontSize: 22,
          }}
        >
          <SafetyCertificateOutlined />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{t("app.title")}</div>
          <Text type="secondary" style={{ fontSize: 11.5 }}>
            {t("app.subtitle")}
          </Text>
        </div>
      </div>

      <Menu
        mode="inline"
        theme={mode === "dark" ? "dark" : "light"}
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => go(key)}
        style={{ flex: 1, borderInlineEnd: 0, background: "transparent", padding: "0 8px" }}
      />

      <div style={{ padding: 12, borderTop: `1px solid ${token.colorBorderSecondary}` }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 10px",
            borderRadius: 11,
            background: token.colorFillTertiary,
          }}
        >
          <Avatar style={{ background: token.colorPrimary, flex: "none" }}>
            {initial}
          </Avatar>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {identity?.name || identity?.username || "—"}
            </div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {identity?.role_name || ""}
            </Text>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {!isMobile && (
        <Sider
          width={SIDER_WIDTH}
          theme={mode === "dark" ? "dark" : "light"}
          style={{
            position: "sticky",
            insetBlockStart: 0,
            height: "100vh",
            background: token.colorBgContainer,
            borderInlineStart: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          {sideContent}
        </Sider>
      )}

      <Drawer
        placement={isRtl ? "right" : "left"}
        open={isMobile && drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={SIDER_WIDTH}
        styles={{ body: { padding: 0 } }}
      >
        {sideContent}
      </Drawer>

      <Layout style={{ background: token.colorBgLayout }}>
        <Header
          style={{
            position: "sticky",
            insetBlockStart: 0,
            zIndex: 10,
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "0 16px",
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          {isMobile && (
            <Button type="text" icon={<MenuOutlined />} onClick={() => setDrawerOpen(true)} />
          )}
          <div style={{ fontWeight: 800, fontSize: 16, whiteSpace: "nowrap" }}>
            {t(TITLE_KEYS[selectedKey] || "app.title")}
          </div>
          <div style={{ flex: 1 }} />
          {!isMobile && (
            <Input
              prefix={<SearchOutlined />}
              placeholder={t("header.search")}
              style={{ maxWidth: 280 }}
            />
          )}
          <Tooltip title={t("common.language")}>
            <Button type="text" icon={<TranslationOutlined />} onClick={toggleLang}>
              {i18n.language === "fa" ? "EN" : "FA"}
            </Button>
          </Tooltip>
          <Tooltip title={t("common.calendar")}>
            <Button
              type="text"
              icon={<CalendarOutlined />}
              onClick={() =>
                setCalendar(calendar === "jalali" ? "gregorian" : "jalali")
              }
            >
              {calendar === "jalali"
                ? t("common.calendar_jalali")
                : t("common.calendar_gregorian")}
            </Button>
          </Tooltip>
          <Dropdown
            trigger={["click"]}
            menu={{
              selectable: true,
              selectedKeys: [font],
              onClick: ({ key }) => setFont(key),
              items: FONT_KEYS.map((k) => ({
                key: k,
                label: (
                  <span style={{ fontFamily: FONTS[k] }}>{FONT_LABELS[k] ?? k}</span>
                ),
              })),
            }}
          >
            <Tooltip title={t("common.font")}>
              <Button type="text" icon={<FontSizeOutlined />} />
            </Tooltip>
          </Dropdown>
          <Dropdown
            trigger={["click"]}
            menu={{
              selectable: true,
              selectedKeys: [accent],
              onClick: ({ key }) => setAccent(key),
              items: ACCENT_KEYS.map((k) => ({
                key: k,
                label: (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: 6,
                        background: accentColor(k, mode),
                        display: "inline-block",
                      }}
                    />
                    {t(`common.accent_${k}`)}
                  </span>
                ),
              })),
            }}
          >
            <Tooltip title={t("common.accent")}>
              <Button
                type="text"
                icon={<BgColorsOutlined style={{ color: accentColor(accent, mode) }} />}
              />
            </Tooltip>
          </Dropdown>
          <Tooltip title={t("common.theme")}>
            <Button type="text" icon={<BulbOutlined />} onClick={toggle} />
          </Tooltip>
          <Tooltip title={t("header.notifications")}>
            <Button type="text" icon={<BellOutlined />} />
          </Tooltip>
          <Tooltip title={t("common.logout")}>
            <Button type="text" danger icon={<LogoutOutlined />} onClick={() => logout()} />
          </Tooltip>
        </Header>

        <Content style={{ padding: isMobile ? 16 : 24, overflow: "auto" }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
