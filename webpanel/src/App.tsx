import { useEffect, useState } from "react";
import { Authenticated, Refine } from "@refinedev/core";
import { useNotificationProvider } from "@refinedev/antd";
import routerProvider, { CatchAllNavigate } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import { App as AntdApp, ConfigProvider } from "antd";
import faIR from "antd/locale/fa_IR";
import enUS from "antd/locale/en_US";
import { useTranslation } from "react-i18next";

import { authProvider } from "./providers/authProvider";
import { dataProvider } from "./providers/dataProvider";
import { makeTheme, fontFamily } from "./theme";
import {
  ColorModeContext,
  type ColorMode,
  type Calendar,
  type Density,
} from "./contexts/color-mode";
import { setCalendarPref } from "./utils/datetime";
import { AppLayout } from "./components/Layout";
import { LoginPage } from "./pages/login";
import { DashboardPage } from "./pages/dashboard";
import { UserList } from "./pages/users/list";
import { UserShow } from "./pages/users/show";
import { ServerList } from "./pages/servers/list";
import { ServiceList } from "./pages/services/list";
import { ProxyList } from "./pages/proxies/list";
import { TransactionList } from "./pages/transactions/list";
import { ReportsPage } from "./pages/reports";
import { ResellerList } from "./pages/resellers/list";
import { ResellerShow } from "./pages/resellers/show";
import { DiscountList } from "./pages/discounts/list";
import { AutomationPage } from "./pages/automation";
import { SettingsPage } from "./pages/settings";
import { GatewaysPage } from "./pages/gateways";
import { AuditPage } from "./pages/audit";
import { TextsPage } from "./pages/texts";
import { MenusPage } from "./pages/menus";
import { ButtonsPage } from "./pages/buttons";

export default function App() {
  const [mode, setModeState] = useState<ColorMode>(
    (localStorage.getItem("theme") as ColorMode) || "dark",
  );
  const [accent, setAccentState] = useState<string>(
    localStorage.getItem("accent") || "emerald",
  );
  const [calendar, setCalendarState] = useState<Calendar>(
    (localStorage.getItem("calendar") as Calendar) || "jalali",
  );
  const [font, setFontState] = useState<string>(
    localStorage.getItem("font") || "vazirmatn",
  );
  const [density, setDensityState] = useState<Density>(
    (localStorage.getItem("density") as Density) || "default",
  );
  const { i18n } = useTranslation();
  const direction: "rtl" | "ltr" = i18n.language === "en" ? "ltr" : "rtl";

  const setMode = (next: ColorMode) => {
    setModeState(next);
    localStorage.setItem("theme", next);
  };

  const toggle = () => setMode(mode === "dark" ? "light" : "dark");

  const setAccent = (a: string) => {
    setAccentState(a);
    localStorage.setItem("accent", a);
  };

  const setDensity = (d: Density) => {
    setDensityState(d);
    localStorage.setItem("density", d);
  };

  const setCalendar = (c: Calendar) => {
    setCalendarState(c);
    setCalendarPref(c); // keep the datetime module + localStorage in sync
  };

  const setFont = (f: string) => {
    setFontState(f);
    localStorage.setItem("font", f);
  };

  useEffect(() => {
    document.documentElement.dir = direction;
    document.documentElement.lang = i18n.language;
  }, [direction, i18n.language]);

  useEffect(() => {
    // Apply the font to non-AntD text (body) too; AntD reads it from the theme.
    document.body.style.fontFamily = fontFamily(font);
  }, [font]);

  return (
    <BrowserRouter>
      <ColorModeContext.Provider
        value={{
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
        }}
      >
        <ConfigProvider
          direction={direction}
          locale={direction === "rtl" ? faIR : enUS}
          theme={makeTheme(accent, mode, font, density)}
        >
          <AntdApp>
            <Refine
              dataProvider={dataProvider}
              authProvider={authProvider}
              routerProvider={routerProvider}
              notificationProvider={useNotificationProvider}
              resources={[
                { name: "dashboard", list: "/", meta: { label: "Dashboard" } },
                {
                  name: "users",
                  list: "/users",
                  show: "/users/show/:id",
                  meta: { label: "Users" },
                },
                { name: "proxies", list: "/proxies", meta: { label: "Subscriptions" } },
                { name: "services", list: "/services", meta: { label: "Services" } },
                { name: "menus", list: "/menus", meta: { label: "Service Menus" } },
                { name: "transactions", list: "/transactions", meta: { label: "Payments" } },
                { name: "servers", list: "/servers", meta: { label: "Panels" } },
                { name: "reports", list: "/reports", meta: { label: "Reports" } },
                {
                  name: "resellers",
                  list: "/resellers",
                  show: "/resellers/show/:id",
                  meta: { label: "Resellers" },
                },
                { name: "discounts", list: "/discounts", meta: { label: "Discounts" } },
                { name: "automation", list: "/automation", meta: { label: "Automation" } },
                { name: "audit", list: "/audit", meta: { label: "Audit" } },
                { name: "texts", list: "/texts", meta: { label: "Texts" } },
                { name: "buttons", list: "/buttons", meta: { label: "Buttons" } },
                { name: "gateways", list: "/gateways", meta: { label: "Payment Gateways" } },
                { name: "settings", list: "/settings", meta: { label: "Settings" } },
              ]}
              options={{ syncWithLocation: true, disableTelemetry: true }}
            >
              <Routes>
                <Route
                  element={
                    <Authenticated
                      key="protected"
                      fallback={<CatchAllNavigate to="/login" />}
                    >
                      <AppLayout>
                        <Outlet />
                      </AppLayout>
                    </Authenticated>
                  }
                >
                  <Route index element={<DashboardPage />} />
                  <Route path="/users" element={<UserList />} />
                  <Route path="/users/show/:id" element={<UserShow />} />
                  <Route path="/proxies" element={<ProxyList />} />
                  <Route path="/services" element={<ServiceList />} />
                  <Route path="/menus" element={<MenusPage />} />
                  <Route path="/transactions" element={<TransactionList />} />
                  <Route path="/servers" element={<ServerList />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/resellers" element={<ResellerList />} />
                  <Route path="/resellers/show/:id" element={<ResellerShow />} />
                  <Route path="/discounts" element={<DiscountList />} />
                  <Route path="/automation" element={<AutomationPage />} />
                  <Route path="/audit" element={<AuditPage />} />
                  <Route path="/texts" element={<TextsPage />} />
                  <Route path="/buttons" element={<ButtonsPage />} />
                  <Route path="/gateways" element={<GatewaysPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>

                <Route
                  element={
                    <Authenticated key="auth-pages" fallback={<Outlet />}>
                      <CatchAllNavigate to="/" />
                    </Authenticated>
                  }
                >
                  <Route path="/login" element={<LoginPage />} />
                </Route>
              </Routes>
            </Refine>
          </AntdApp>
        </ConfigProvider>
      </ColorModeContext.Provider>
    </BrowserRouter>
  );
}
