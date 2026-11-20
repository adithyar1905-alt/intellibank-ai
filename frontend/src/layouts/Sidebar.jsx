import {
  Activity, ArrowDownUp, BadgeDollarSign, Banknote, Bell, Bot, BriefcaseBusiness,
  ChartNoAxesCombined, ChevronDown, ChevronLeft, CircleDollarSign, ClipboardList,
  Clock3, CreditCard, FileBarChart, Fingerprint, Gauge, Landmark, LayoutDashboard,
  ListChecks, Radar, Search, Settings, ShieldAlert, ShieldCheck,
  UserRoundSearch, Users, WalletCards,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../app/AuthContext.jsx";

const items = [
  { label: "Overview", path: "/", icon: LayoutDashboard, description: "Bank-wide activity, portfolio summaries, and operational insights." },
  { label: "Customers", path: "/customers", icon: Users, description: "Customer profiles, KYC progress, and relationship history." },
  {
    label: "Accounts", path: "/accounts", icon: WalletCards, description: "Account directory, balances, status, and account servicing.",
    submenu: [
      { label: "Account Overview", view: "overview", icon: LayoutDashboard, description: "Review account totals, statuses, and balances." },
      { label: "Account Applications", view: "applications", icon: ClipboardList, description: "Review newly submitted account applications." },
      { label: "Account Limits", view: "limits", icon: Gauge, description: "Review account transaction and withdrawal limits." },
      { label: "Statements", view: "statements", icon: FileBarChart, description: "Browse account statements and activity summaries." },
      { label: "Account Activity", view: "activity", icon: Activity, description: "Review recent activity across customer accounts." },
    ],
  },
  {
    label: "Transactions", path: "/transactions", icon: Activity, description: "Transaction activity, statuses, and monitoring.",
    submenu: [
      { label: "Transaction Overview", view: "overview", icon: LayoutDashboard, description: "See transaction volume, totals, and status summaries." },
      { label: "Fund Transfers", view: "fund-transfers", icon: ArrowDownUp, description: "Review internal and external fund transfers." },
      { label: "Payment History", view: "payment-history", icon: Clock3, description: "Browse completed and historical transactions." },
      { label: "Pending Transactions", view: "pending", icon: Clock3, description: "Find transactions awaiting processing or review." },
      { label: "Transaction Monitoring", view: "monitoring", icon: Radar, description: "Monitor transaction activity and risk indicators." },
    ],
  },
  {
    label: "Payments", path: "/payments", icon: CreditCard, description: "Payment channels, history, and payment status.",
    submenu: [
      { label: "Payment Overview", view: "overview", icon: LayoutDashboard, description: "Review payment volumes and channel performance." },
      { label: "UPI Payments", view: "upi", icon: CircleDollarSign, description: "Browse UPI payment activity and status." },
      { label: "NEFT Transfers", view: "neft", icon: ArrowDownUp, description: "Review NEFT transfer history." },
      { label: "RTGS Transfers", view: "rtgs", icon: Banknote, description: "Review RTGS transfer history." },
      { label: "IMPS Payments", view: "imps", icon: Activity, description: "Browse IMPS payments and their status." },
      { label: "Failed Payments", view: "failed", icon: CircleDollarSign, description: "Review failed payments and their recorded outcomes." },
    ],
  },
  {
    label: "Loans", path: "/loans", icon: BriefcaseBusiness, description: "Loan applications, approvals, and repayment operations.",
    submenu: [
      { label: "Loan Overview", view: "overview", icon: LayoutDashboard, description: "Review loan portfolio and application status summaries." },
      { label: "Loan Applications", view: "applications", icon: ClipboardList, description: "Review customer loan applications." },
      { label: "Loan Approvals", view: "approvals", icon: BadgeDollarSign, description: "View loans awaiting or completing approval." },
      { label: "Repayment Tracking", view: "repayments", icon: Clock3, description: "Monitor repayment schedules and payment progress." },
      { label: "Credit Analysis", view: "credit-analysis", icon: Fingerprint, description: "Review credit assessment information for lending." },
    ],
  },
  {
    label: "Fraud Detection", path: "/fraud", icon: ShieldAlert, description: "Illustrative fraud alerts, risk signals, and investigations.",
    submenu: [
      { label: "Fraud Dashboard", view: "overview", icon: LayoutDashboard, description: "See alert summaries and illustrative risk trends." },
      { label: "Real-time Monitoring", view: "monitoring", icon: Radar, description: "Review transaction monitoring signals as they arrive." },
      { label: "Suspicious Transactions", view: "suspicious-transactions", icon: Search, description: "Review transactions flagged for human assessment." },
      { label: "Risk Scoring", view: "risk-scoring", icon: Gauge, description: "Inspect illustrative model scores and risk categories." },
      { label: "Fraud Alerts", view: "alerts", icon: Bell, description: "Review open and resolved fraud alerts." },
      { label: "Investigation Center", view: "investigations", icon: ClipboardList, description: "Track investigation notes, ownership, and outcomes." },
    ],
  },
  {
    label: "Credit Intelligence", path: "/credit-intelligence", icon: Fingerprint, description: "Illustrative customer credit profiles and risk assessments.",
    submenu: [
      { label: "Credit Overview", view: "overview", icon: LayoutDashboard, description: "Review credit profile totals and risk categories." },
      { label: "Customer Credit Profiles", view: "profiles", icon: UserRoundSearch, description: "Browse customer credit assessment profiles." },
      { label: "Risk Categories", view: "risk-categories", icon: ShieldCheck, description: "Compare customers by illustrative risk category." },
      { label: "Loan Eligibility", view: "eligibility", icon: BadgeDollarSign, description: "Review indicative loan eligibility assessments." },
      { label: "Credit Insights", view: "insights", icon: ChartNoAxesCombined, description: "Explore model insights and assessment limitations." },
    ],
  },
  {
    label: "AML & Compliance", path: "/aml", icon: ShieldCheck, description: "Compliance alerts, cases, and human-led investigations.",
    submenu: [
      { label: "AML Overview", view: "overview", icon: LayoutDashboard, description: "Review open cases and compliance activity." },
      { label: "Suspicious Activity", view: "suspicious-activity", icon: Radar, description: "Browse activity flagged for compliance review." },
      { label: "High-Risk Customers", view: "high-risk-customers", icon: UserRoundSearch, description: "Review customers with elevated risk indicators." },
      { label: "Compliance Cases", view: "cases", icon: ClipboardList, description: "Manage case status and investigation ownership." },
      { label: "Investigations", view: "investigations", icon: Search, description: "Follow human-led compliance investigation workflows." },
      { label: "Compliance Reports", view: "reports", icon: FileBarChart, description: "Review compliance reports and case summaries." },
    ],
  },
  {
    label: "AI Assistant", path: "/assistant", icon: Bot, description: "Read-only banking guidance with safe assistant controls.",
    submenu: [
      { label: "Assistant Home", view: "overview", icon: Bot, description: "Start a guided, read-only assistant conversation." },
      { label: "Customer Insights", view: "customer-insights", icon: UserRoundSearch, description: "Ask supported questions about authorized customer information." },
      { label: "Transaction Analysis", view: "transaction-analysis", icon: ArrowDownUp, description: "Explore transaction questions without initiating transfers." },
      { label: "Fraud Investigation", view: "fraud-investigation", icon: ShieldAlert, description: "Get assistance reviewing fraud investigation information." },
      { label: "Banking FAQs", view: "faqs", icon: CircleDollarSign, description: "Ask general banking and financial education questions." },
    ],
  },
  {
    label: "Analytics", path: "/analytics", icon: ChartNoAxesCombined, description: "Illustrative financial, customer, and risk analytics.",
    submenu: [
      { label: "Analytics Overview", view: "overview", icon: LayoutDashboard, description: "Explore high-level banking performance indicators." },
      { label: "Customer Growth", view: "customer-growth", icon: Users, description: "Review customer growth and registration trends." },
      { label: "Transaction Analytics", view: "transactions", icon: ArrowDownUp, description: "Analyze transaction volumes and activity patterns." },
      { label: "Deposit Analytics", view: "deposits", icon: Banknote, description: "Review deposit trends and balance summaries." },
      { label: "Loan Analytics", view: "loans", icon: BriefcaseBusiness, description: "Explore loan portfolio and application trends." },
      { label: "Fraud Analytics", view: "fraud", icon: ShieldAlert, description: "Review illustrative fraud alerts and risk patterns." },
    ],
  },
  { label: "Reports", path: "/reports", icon: FileBarChart, description: "Browse reports and export illustrative sample data." },
  { label: "Notifications", path: "/notifications", icon: ClipboardList, description: "Review banking, system, and risk notifications." },
  { label: "Audit Logs", path: "/audit-logs", icon: ListChecks, description: "Review audit events and administrative activity." },
  { label: "Settings", path: "/settings", icon: Settings, description: "Manage your profile, security, and assigned access." },
];

export default function Sidebar({ open, onClose, collapsed, onCollapse }) {
  const { user, isDemo } = useAuth();
  const location = useLocation();
  const activeItem = items.find((item) => item.path === location.pathname);
  const [expanded, setExpanded] = useState(() => activeItem?.submenu ? [activeItem.path] : []);
  const [tooltip, setTooltip] = useState(null);
  const selectedView = new URLSearchParams(location.search).get("view");
  const roles = user?.roles || [];
  const privileged = isDemo || roles.includes("Super Admin") || roles.includes("Bank Admin");
  const staffRoles = ["Super Admin", "Bank Admin", "Branch Manager", "Bank Employee"];
  const staff = isDemo || roles.some((role) => staffRoles.includes(role));
  const riskStaff = staff || roles.includes("Risk Analyst");
  const loanStaff = staff || roles.includes("Loan Officer");
  const allowed = (path) => {
    if (privileged || path === "/settings") return true;
    if (path === "/customers") return staff;
    if (path === "/accounts" || path === "/transactions") return staff || roles.includes("Customer");
    if (path === "/loans") return loanStaff || roles.includes("Customer");
    if (path === "/credit-intelligence") return loanStaff || roles.includes("Risk Analyst") || roles.includes("Customer");
    if (path === "/fraud" || path === "/aml") return riskStaff;
    if (path === "/assistant") return roles.includes("Customer");
    if (path === "/") return staff || roles.includes("Risk Analyst") || roles.includes("Loan Officer");
    return staff;
  };
  useEffect(() => {
    if (activeItem?.submenu) {
      setExpanded((current) => current.includes(activeItem.path) ? current : [...current, activeItem.path]);
    }
  }, [activeItem?.path]);

  function toggleSubmenu(path) {
    setExpanded((current) => current.includes(path)
      ? current.filter((itemPath) => itemPath !== path)
      : [...current, path]);
  }

  function showTooltip(title, description, element) {
    const bounds = element.getBoundingClientRect();
    setTooltip({
      title,
      description,
      top: Math.max(50, Math.min(bounds.top + bounds.height / 2, window.innerHeight - 55)),
      left: Math.min(bounds.right + 10, window.innerWidth - 120),
      width: Math.min(230, window.innerWidth - Math.min(bounds.right + 10, window.innerWidth - 120) - 12),
    });
  }

  function hideTooltip() {
    setTooltip(null);
  }

  return (
    <>
      {open && <button className="sidebar-scrim" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${open ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-emblem" aria-hidden="true">
            <div className="brand-mark"><Landmark size={21} /></div>
          </div>
          {!collapsed && <div className="brand-name">IntelliBank <span>AI</span><small>ENTERPRISE BANKING</small></div>}
          <button className="collapse-button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} onClick={onCollapse}><ChevronLeft size={16} /></button>
        </div>
        <div className="nav-caption">{!collapsed && "WORKSPACE"}</div>
        <nav className="side-nav" aria-label="Main navigation">
          {items.filter(({ path }) => allowed(path)).map(({ label, path, icon: Icon, description, submenu }) => {
            const isExpanded = expanded.includes(path);
            return (
              <div className={`nav-group ${isExpanded ? "submenu-open" : ""}`} key={path}>
                <div className="nav-row">
                  <NavLink
                    className="nav-link"
                    to={path}
                    title={collapsed ? `${label}: ${description}` : undefined}
                    data-tooltip-title={label}
                    data-tooltip-description={description}
                    onClick={() => { if (submenu && collapsed) toggleSubmenu(path); onClose(); }}
                    onPointerEnter={(event) => showTooltip(label, description, event.currentTarget)}
                    onPointerLeave={hideTooltip}
                    onFocus={(event) => showTooltip(label, description, event.currentTarget)}
                    onBlur={hideTooltip}
                    end={path === "/"}
                  >
                    <Icon size={18} />
                    <span>{label}</span>
                    {label === "Fraud Detection" && <i className="nav-count">3</i>}
                  </NavLink>
                  {submenu && !collapsed && (
                    <button className="nav-toggle" aria-label={`${isExpanded ? "Collapse" : "Expand"} ${label} submenu`} aria-expanded={isExpanded} onClick={() => toggleSubmenu(path)}>
                      <ChevronDown size={15} />
                    </button>
                  )}
                </div>
                {submenu && (
                  <div className="nav-submenu" aria-label={`${label} submenu`} aria-hidden={!isExpanded}>
                    <div className="nav-submenu-inner">
                      {submenu.map(({ label: childLabel, view, icon: ChildIcon, description: childDescription }) => (
                        <NavLink
                          key={view}
                          className={`nav-sub-link ${location.pathname === path && selectedView === view ? "selected-sub-link" : ""}`}
                          to={`${path}?view=${encodeURIComponent(view)}`}
                          tabIndex={isExpanded ? 0 : -1}
                          aria-current={location.pathname === path && selectedView === view ? "page" : undefined}
                          data-tooltip-title={childLabel}
                          data-tooltip-description={childDescription}
                          onClick={onClose}
                          onPointerEnter={(event) => showTooltip(childLabel, childDescription, event.currentTarget)}
                          onPointerLeave={hideTooltip}
                          onFocus={(event) => showTooltip(childLabel, childDescription, event.currentTarget)}
                          onBlur={hideTooltip}
                        >
                          <ChildIcon size={15} />
                          <span>{childLabel}</span>
                        </NavLink>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </nav>
        {!collapsed && <div className="sidebar-footer"><div className="secure-dot" /> Secure operations <span>v1.0</span></div>}
      </aside>
      {tooltip && <div className="nav-hover-tooltip" role="tooltip" style={{ top: tooltip.top, left: tooltip.left, width: tooltip.width }}>
        <strong>{tooltip.title}</strong>
        <span>{tooltip.description}</span>
      </div>}
    </>
  );
}
