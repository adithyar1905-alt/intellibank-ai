import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";
import AppLayout from "../layouts/AppLayout.jsx";

const Dashboard = lazy(() => import("../pages/Dashboard.jsx"));
const Customers = lazy(() => import("../pages/Customers.jsx"));
const Accounts = lazy(() => import("../pages/Accounts.jsx"));
const Transactions = lazy(() => import("../pages/Transactions.jsx"));
const Payments = lazy(() => import("../pages/Payments.jsx"));
const Loans = lazy(() => import("../pages/Loans.jsx"));
const Fraud = lazy(() => import("../pages/Fraud.jsx"));
const CreditIntelligence = lazy(() => import("../pages/CreditIntelligence.jsx"));
const AML = lazy(() => import("../pages/AML.jsx"));
const Assistant = lazy(() => import("../pages/Assistant.jsx"));
const Analytics = lazy(() => import("../pages/Analytics.jsx"));
const Reports = lazy(() => import("../pages/Reports.jsx"));
const Notifications = lazy(() => import("../pages/Notifications.jsx"));
const AuditLogs = lazy(() => import("../pages/AuditLogs.jsx"));
const Settings = lazy(() => import("../pages/Settings.jsx"));
const Login = lazy(() => import("../pages/Login.jsx"));

export default function App() {
  const { loading, user, isDemo } = useAuth();
  if (loading) return <div className="app-loading">Loading IntelliBank AI…</div>;
  const roles = user?.roles || [];
  const privileged = isDemo || roles.includes("Super Admin") || roles.includes("Bank Admin");
  const staffRoles = ["Super Admin", "Bank Admin", "Branch Manager", "Bank Employee"];
  const staff = isDemo || roles.some((role) => staffRoles.includes(role));
  const riskStaff = staff || roles.includes("Risk Analyst");
  const loanStaff = staff || roles.includes("Loan Officer");
  const allowed = {
    "/": staff || roles.includes("Loan Officer") || roles.includes("Risk Analyst"),
    "/customers": staff,
    "/accounts": staff || roles.includes("Customer"),
    "/transactions": staff || roles.includes("Customer"),
    "/payments": staff,
    "/loans": loanStaff || roles.includes("Customer"),
    "/fraud": riskStaff,
    "/credit-intelligence": loanStaff || roles.includes("Risk Analyst") || roles.includes("Customer"),
    "/aml": riskStaff,
    "/assistant": roles.includes("Customer") || isDemo,
    "/analytics": staff,
    "/reports": staff,
    "/notifications": staff,
    "/audit-logs": privileged,
    "/settings": true,
  };
  const page = (path, component) => allowed[path]
    ? <AppLayout>{component}</AppLayout>
    : <AppLayout><div className="access-denied"><h1>Access restricted</h1><p>Your assigned role does not have access to this administration module.</p></div></AppLayout>;
  return <Suspense fallback={<div className="app-loading">Loading module…</div>}>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={page("/", <Dashboard />)} />
      <Route path="/customers" element={page("/customers", <Customers />)} />
      <Route path="/accounts" element={page("/accounts", <Accounts />)} />
      <Route path="/transactions" element={page("/transactions", <Transactions />)} />
      <Route path="/payments" element={page("/payments", <Payments />)} />
      <Route path="/loans" element={page("/loans", <Loans />)} />
      <Route path="/fraud" element={page("/fraud", <Fraud />)} />
      <Route path="/credit-intelligence" element={page("/credit-intelligence", <CreditIntelligence />)} />
      <Route path="/aml" element={page("/aml", <AML />)} />
      <Route path="/assistant" element={page("/assistant", <Assistant />)} />
      <Route path="/analytics" element={page("/analytics", <Analytics />)} />
      <Route path="/reports" element={page("/reports", <Reports />)} />
      <Route path="/notifications" element={page("/notifications", <Notifications />)} />
      <Route path="/audit-logs" element={page("/audit-logs", <AuditLogs />)} />
      <Route path="/settings" element={page("/settings", <Settings />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>;
}
