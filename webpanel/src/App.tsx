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
import { darkTheme, lightTheme } from "./theme";
import { ColorModeContext, type ColorMode } from "./contexts/color-mode";
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

export default function App() {
  const [mode, setMode] = useState<ColorMode>(
    (localStorage.getItem("theme") as ColorMode) || "dark",
  );
  const { i18n } = useTranslation();
  const direction: "rtl" | "ltr" = i18n.language === "en" ? "ltr" : "rtl";

  const toggle = () => {
    const next = mode === "dark" ? "light" : "dark";
    setMode(next);
    localStorage.setItem("theme", next);
  };

  useEffect(() => {
    document.documentElement.dir = direction;
    document.documentElement.lang = i18n.language;
  }, [direction, i18n.language]);

  return (
    <BrowserRouter>
      <ColorModeContext.Provider value={{ mode, toggle }}>
        <ConfigProvider
          direction={direction}
          locale={direction === "rtl" ? faIR : enUS}
          theme={mode === "dark" ? darkTheme : lightTheme}
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
                  <Route path="/transactions" element={<TransactionList />} />
                  <Route path="/servers" element={<ServerList />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/resellers" element={<ResellerList />} />
                  <Route path="/resellers/show/:id" element={<ResellerShow />} />
                  <Route path="/discounts" element={<DiscountList />} />
                  <Route path="/automation" element={<AutomationPage />} />
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
