import { useMemo } from "react";
import { ClipboardList, Info, ShieldCheck } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const demoAudit = [
  { id: "AUD-8811", actor: "admin@intellibank.ai", action: "customer.profile_read", resource: "CUS-20481", source: "10.0.2.14", created_at: "2025-02-18T14:34:00Z", status: "success" },
  { id: "AUD-8810", actor: "risk.analyst@intellibank.ai", action: "fraud.alert_reviewed", resource: "ALT-7201", source: "10.0.2.19", created_at: "2025-02-18T14:25:00Z", status: "success" },
  { id: "AUD-8809", actor: "loan.officer@intellibank.ai", action: "loan.application_reviewed", resource: "APP-9001", source: "10.0.2.22", created_at: "2025-02-18T13:50:00Z", status: "success" },
  { id: "AUD-8808", actor: "admin@intellibank.ai", action: "auth.login", resource: "USR-1001", source: "10.0.2.14", created_at: "2025-02-18T08:02:00Z", status: "success" },
];

export default function AuditLogs() {
  const columns = useMemo(() => [
    { key: "id", label: "Event ID", render: (row) => <strong className="mono">{row.id}</strong> },
    { key: "actor", label: "Actor" },
    { key: "action", label: "Activity", render: (row) => <span className="mono">{row.action}</span> },
    { key: "resource", label: "Resource", render: (row) => <span className="mono">{row.resource}</span> },
    { key: "source", label: "Source" },
    { key: "created_at", label: "Timestamp", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "status", label: "Result", render: (row) => <StatusBadge value={row.status} /> },
  ], []);
  return <div className="page-stack">
    <PageHeader eyebrow="GOVERNANCE" title="Audit logs" description="Review administrative activity, sign-ins, and monitored changes." action={<button className="button button-outline" onClick={() => window.print()}><ClipboardList size={16} /> Print view</button>} />
    <div className="demo-notice"><Info size={16} /> Audit APIs are not mounted in the current backend app. Entries below are illustrative and are not authoritative audit records.</div>
    <div className="metric-grid three">
      <MetricCard title="Events today" value="128" note="illustrative activity count" icon={ClipboardList} tone="blue" />
      <MetricCard title="Successful actions" value="124" note="sample audit entries" icon={ShieldCheck} tone="teal" />
      <MetricCard title="Security events" value="4" note="illustrative review count" icon={ShieldCheck} tone="amber" />
    </div>
    <Panel title="Activity log" description="Filter by actor, event type, resource, or timestamp"><DataTable columns={columns} rows={demoAudit} searchPlaceholder="Search audit events…" /></Panel>
  </div>;
}
