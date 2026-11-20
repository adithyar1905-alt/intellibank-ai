import { useMemo, useState } from "react";
import { Bell, CheckCheck, CircleAlert, Info, ShieldAlert } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const initialNotifications = [
  { id: "NTF-001", title: "High-risk transfer held for review", category: "Fraud alert", detail: "Transaction TXN-591841 requires authorized human review.", created_at: "2025-02-18T14:22:00Z", status: "unread", icon: ShieldAlert },
  { id: "NTF-002", title: "Loan application submitted", category: "Loan approval", detail: "Application APP-9002 entered the review queue.", created_at: "2025-02-18T11:16:00Z", status: "unread", icon: Bell },
  { id: "NTF-003", title: "Daily service health check passed", category: "System", detail: "All configured API services are responding normally.", created_at: "2025-02-18T09:00:00Z", status: "read", icon: Info },
  { id: "NTF-004", title: "Customer KYC documents pending", category: "Customer alert", detail: "One customer profile has documents awaiting verification.", created_at: "2025-02-17T17:34:00Z", status: "read", icon: CircleAlert },
];

export default function Notifications() {
  const [notifications, setNotifications] = useState(initialNotifications);
  const columns = useMemo(() => [
    { key: "title", label: "Notification", render: (row) => <div className="table-person"><span className="mini-icon amber"><row.icon size={16} /></span><span><strong>{row.title}</strong><small>{row.detail}</small></span></div> },
    { key: "category", label: "Category" },
    { key: "created_at", label: "Received", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", label: "", render: (row) => row.status === "unread" ? <button className="button button-quiet" onClick={() => setNotifications(notifications.map((item) => item.id === row.id ? { ...item, status: "read" } : item))}>Mark read</button> : null },
  ], [notifications]);
  return <div className="page-stack">
    <PageHeader eyebrow="ALERT CENTER" title="Notifications" description="Banking, system, loan, and risk alerts for administrators." action={<button className="button button-outline" onClick={() => setNotifications(notifications.map((item) => ({ ...item, status: "read" })))}><CheckCheck size={16} /> Mark all read</button>} />
    <div className="demo-notice"><CircleAlert size={16} /> Notifications are demonstration content; there is no mounted notification API.</div>
    <Panel title="Notification inbox" description={`${notifications.filter((item) => item.status === "unread").length} unread notifications`}><DataTable columns={columns} rows={notifications} searchPlaceholder="Search notifications…" /></Panel>
  </div>;
}
