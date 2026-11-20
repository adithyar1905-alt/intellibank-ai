import { useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

export default function AppLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const routeKey = `${location.pathname}${location.search}`;
  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} collapsed={collapsed} onCollapse={() => setCollapsed(!collapsed)} />
      <div className="main-shell">
        <Topbar onMenu={() => setSidebarOpen(true)} />
        <main className="main-content">
          <div className="route-transition" key={routeKey}>{children}</div>
        </main>
        <footer className="app-footer">© 2025 IntelliBank AI <span>Secure enterprise banking operations</span></footer>
      </div>
    </div>
  );
}
