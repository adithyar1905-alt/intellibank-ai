import { Bell, CircleHelp, LogIn, LogOut, Menu, Search, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext.jsx";
import { demoCustomers } from "../data/demo.js";

const destinations = [
  { label: "Overview", path: "/" }, { label: "Customers", path: "/customers" },
  { label: "Accounts", path: "/accounts" }, { label: "Transactions", path: "/transactions" },
  { label: "Payments", path: "/payments" }, { label: "Loans", path: "/loans" },
  { label: "Fraud Detection", path: "/fraud" }, { label: "Credit Intelligence", path: "/credit-intelligence" },
  { label: "AML & Compliance", path: "/aml" }, { label: "AI Assistant", path: "/assistant" },
  { label: "Analytics", path: "/analytics" }, { label: "Reports", path: "/reports" },
  { label: "Notifications", path: "/notifications" }, { label: "Audit Logs", path: "/audit-logs" },
  ...demoCustomers.slice(0, 3).map((customer) => ({ label: `${customer.first_name} ${customer.last_name}`, path: "/customers" })),
];

export default function Topbar({ onMenu }) {
  const { user, isDemo, logout } = useAuth();
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const menuRef = useRef(null);
  const searchRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const close = (event) => !menuRef.current?.contains(event.target) && setMenuOpen(false);
    const shortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", shortcut);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", shortcut);
    };
  }, []);

  function onSearch(event) {
    const value = event.target.value;
    setSearch(value);
    setMatches(value.trim() ? destinations.filter((item) => item.label.toLowerCase().includes(value.toLowerCase())).slice(0, 6) : []);
  }

  return (
    <header className="topbar">
      <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={onMenu}><Menu size={20} /></button>
      <div className="global-search">
        <Search size={17} />
        <input ref={searchRef} aria-label="Global search" value={search} onChange={onSearch} onKeyDown={(event) => event.key === "Enter" && matches[0] && navigate(matches[0].path)} placeholder="Search customers, accounts, transactions…" />
        <kbd>⌘ K</kbd>
        {matches.length > 0 && <div className="search-results">{matches.map((item) => <button key={`${item.label}-${item.path}`} onClick={() => { navigate(item.path); setSearch(""); setMatches([]); }}>{item.label}<span>Open</span></button>)}</div>}
      </div>
      {isDemo && <span className="demo-pill">DEMO DATA</span>}
      {feedback && <span className="topbar-feedback" role="status">{feedback}</span>}
      <div className="topbar-actions">
        <button className="icon-button notification-button" aria-label="Notifications" onClick={() => navigate("/notifications")}><Bell size={19} /><i /></button>
        <button className="icon-button help-button" aria-label="Help" onClick={() => navigate("/assistant")}><CircleHelp size={19} /></button>
        <div className="profile-wrap" ref={menuRef}>
          <button className="profile-trigger" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}>
            <span className="avatar"><UserRound size={18} /></span>
            <span className="profile-copy"><strong>{user?.name || "Admin User"}</strong><small>{user?.roles?.[0] || "Administrator"}</small></span>
            <span className="profile-caret">⌄</span>
          </button>
          {menuOpen && <div className="profile-menu">
            <div className="profile-menu-heading">{user?.email}</div>
            <button onClick={() => { navigate("/settings"); setMenuOpen(false); }}><UserRound size={16} /> Profile & settings</button>
            {isDemo
              ? <button onClick={() => { navigate("/login"); setMenuOpen(false); }}><LogIn size={16} /> Connect to backend</button>
              : <button onClick={async () => { try { await logout(); setFeedback(""); } catch { setFeedback("Signed out locally; server revocation failed."); } finally { setMenuOpen(false); } }}><LogOut size={16} /> Sign out</button>}
          </div>}
        </div>
      </div>
    </header>
  );
}
