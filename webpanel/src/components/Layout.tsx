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
  ColumnHeightOutlined,
  CreditCardOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FontSizeOutlined,
  FormatPainterOutlined,
  LayoutOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SendOutlined,
  SettingOutlined,
  ShopOutlined,
  SkinOutlined,
  TagsOutlined,
  TeamOutlined,
  TranslationOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useGetIdentity, useLogout } from "@refinedev/core";

import { ColorModeContext, type Density } from "../contexts/color-mode";
import { ACCENT_KEYS, accentColor, FONT_KEYS, FONTS, PRESETS } from "../theme";

const FONT_LABELS: Record<string, string> = {
  vazirmatn: "Vazirmatn",
  vazir: "Vazir",
  sahel: "Sahel",
  samim: "Samim",
  system: "System",
};

const { Header, Sider, Content, Footer } = Layout;
const { useBreakpoint } = Grid;
const { Text } = Typography;

const SIDER_WIDTH = 264;
const SIDER_COLLAPSED = 76;

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
  "/gateways": "gateways.title",
  "/settings": "settings.title",
};

export function AppLayout({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const {
    mode,
    toggle,
    setMode,
    accent,
    setAccent,
    calendar,
    setCalendar,
    font,
    setFont,
    density,
    setDensity,
  } = useContext(ColorModeContext);
  const { token } = theme.useToken();
  const screens = useBreakpoint();
  const navigate = useNavigate();
  const location = useLocation();
  const { mutate: logout } = useLogout();
  const { data: identity } = useGetIdentity<Identity>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    localStorage.getItem("sidebar_collapsed") === "1",
  );

  const isMobile = !screens.lg;
  const isRtl = i18n.language !== "en";

  const selectedKey =
    location.pathname === "/" ? "/" : "/" + location.pathname.split("/")[1];

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
                    { key: "/gateways", icon: <CreditCardOutlined />, label: t("nav.gateways") },
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

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar_collapsed", next ? "1" : "0");
  };

  const initial = (identity?.name || identity?.username || "؟").trim().slice(0, 1);
  const mini = collapsed && !isMobile;

  // --- consolidated appearance menu (theme · language · calendar · accent · font) ---
  const appearanceMenu = {
    selectable: false,
    onClick: ({ key, keyPath }: { key: string; keyPath: string[] }) => {
      if (keyPath.includes("accent")) return setAccent(key);
      if (keyPath.includes("font")) return setFont(key);
      if (keyPath.includes("preset")) {
        const p = PRESETS.find((x) => x.key === key);
        if (p) {
          setAccent(p.accent);
          setMode(p.mode);
        }
        return;
      }
      if (keyPath.includes("density")) return setDensity(key as Density);
      if (key === "theme") return toggle();
      if (key === "lang") return toggleLang();
      if (key === "calendar")
        return setCalendar(calendar === "jalali" ? "gregorian" : "jalali");
    },
    items: [
      { key: "theme", icon: <BulbOutlined />, label: `${t("common.theme")} · ${mode === "dark" ? "🌙" : "☀️"}` },
      { key: "lang", icon: <TranslationOutlined />, label: `${t("common.language")} · ${i18n.language === "fa" ? "FA" : "EN"}` },
      { key: "calendar", icon: <CalendarOutlined />, label: `${t("common.calendar")} · ${calendar === "jalali" ? t("common.calendar_jalali") : t("common.calendar_gregorian")}` },
      { type: "divider" as const },
      {
        key: "accent",
        icon: <BgColorsOutlined />,
        label: t("common.accent"),
        children: ACCENT_KEYS.map((k) => ({
          key: k,
          label: (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 12, borderRadius: 6, background: accentColor(k, mode), display: "inline-block", outline: accent === k ? `2px solid ${token.colorPrimary}` : "none", outlineOffset: 1 }} />
              {t(`common.accent_${k}`)}
            </span>
          ),
        })),
      },
      {
        key: "font",
        icon: <FontSizeOutlined />,
        label: t("common.font"),
        children: FONT_KEYS.map((k) => ({
          key: k,
          label: <span style={{ fontFamily: FONTS[k], fontWeight: font === k ? 700 : 400 }}>{FONT_LABELS[k] ?? k}</span>,
        })),
      },
      { type: "divider" as const },
      {
        key: "preset",
        icon: <FormatPainterOutlined />,
        label: t("common.preset"),
        children: PRESETS.map((p) => ({
          key: p.key,
          label: (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 12, borderRadius: 6, background: accentColor(p.accent, p.mode), display: "inline-block" }} />
              {t(`common.preset_${p.key}`)}
              <span style={{ marginInlineStart: "auto", opacity: 0.6 }}>{p.mode === "dark" ? "🌙" : "☀️"}</span>
            </span>
          ),
        })),
      },
      {
        key: "density",
        icon: <ColumnHeightOutlined />,
        label: t("common.density"),
        children: (["default", "compact"] as Density[]).map((d) => ({
          key: d,
          label: <span style={{ fontWeight: density === d ? 700 : 400 }}>{t(`common.density_${d}`)}</span>,
        })),
      },
    ],
  };

  const sideContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: mini ? "center" : "flex-start", gap: 11, padding: mini ? "18px 0 14px" : "18px 18px 14px" }}>
        <div style={{ width: 40, height: 40, borderRadius: 11, background: token.colorPrimary, color: "#fff", display: "grid", placeItems: "center", flex: "none", fontSize: 22 }}>
          <SafetyCertificateOutlined />
        </div>
        {!mini && (
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: 16 }}>{t("app.title")}</div>
            <Text type="secondary" style={{ fontSize: 11.5 }}>{t("app.subtitle")}</Text>
          </div>
        )}
      </div>

      <Menu
        mode="inline"
        inlineCollapsed={mini}
        theme={mode === "dark" ? "dark" : "light"}
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => go(key)}
        style={{ flex: 1, borderInlineEnd: 0, background: "transparent", padding: mini ? "0 6px" : "0 8px", overflowY: "auto" }}
      />

      <div style={{ padding: 12, borderTop: `1px solid ${token.colorBorderSecondary}` }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: mini ? "center" : "flex-start", gap: 10, padding: mini ? 6 : "8px 10px", borderRadius: 11, background: mini ? "transparent" : token.colorFillTertiary }}>
          <Avatar style={{ background: token.colorPrimary, flex: "none" }}>{initial}</Avatar>
          {!mini && (
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {identity?.name || identity?.username || "—"}
              </div>
              <Text type="secondary" style={{ fontSize: 11 }}>{identity?.role_name || ""}</Text>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {!isMobile && (
        <Sider
          width={SIDER_WIDTH}
          collapsedWidth={SIDER_COLLAPSED}
          collapsed={collapsed}
          trigger={null}
          theme={mode === "dark" ? "dark" : "light"}
          style={{ position: "sticky", insetBlockStart: 0, height: "100vh", background: token.colorBgContainer, borderInlineEnd: `1px solid ${token.colorBorderSecondary}` }}
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
            gap: 8,
            padding: isMobile ? "0 12px" : "0 18px",
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Button
            type="text"
            icon={isMobile ? <MenuOutlined /> : collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => (isMobile ? setDrawerOpen(true) : toggleCollapse())}
          />
          <div style={{ fontWeight: 800, fontSize: 16, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {t(TITLE_KEYS[selectedKey] || "app.title")}
          </div>
          <div style={{ flex: 1 }} />
          {!isMobile && (
            <Input prefix={<SearchOutlined />} placeholder={t("header.search")} style={{ maxWidth: 260 }} />
          )}
          <Dropdown trigger={["click"]} menu={appearanceMenu as any} placement="bottomRight">
            <Tooltip title={t("header.appearance")}>
              <Button type="text" icon={<SkinOutlined style={{ color: accentColor(accent, mode) }} />} />
            </Tooltip>
          </Dropdown>
          <Tooltip title={t("header.notifications")}>
            <Button type="text" icon={<BellOutlined />} />
          </Tooltip>
          <Tooltip title={t("common.logout")}>
            <Button type="text" danger icon={<LogoutOutlined />} onClick={() => logout()} />
          </Tooltip>
        </Header>

        <Content style={{ padding: isMobile ? 16 : 24, overflow: "auto" }}>{children}</Content>

        <Footer style={{ textAlign: "center", background: token.colorBgLayout, borderTop: `1px solid ${token.colorBorderSecondary}`, color: token.colorTextTertiary, fontSize: 12, padding: "14px 24px" }}>
          {t("app.title")} · {t("footer.tagline")}
        </Footer>
      </Layout>
    </Layout>
  );
}
