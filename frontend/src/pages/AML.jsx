import { useCallback, useMemo, useState } from "react";
import { AlertTriangle, FileSearch, Scale, ShieldCheck } from "lucide-react";
import { riskService } from "../services/banking.js";
import { demoAmlCases, demoCustomers, fullName } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";

export default function AML() {
  const { isDemo } = useAuth();
  const load = useCallback(async () => {
    const [cases, summary] = await Promise.all([
      riskService.amlCases({ limit: 100 }),
      riskService.amlSummary(),
    ]);
    return { cases: cases.data, summary: summary.data };
  }, []);
  const { data, setData, loading, error, refresh } = useApiResource(load, { cases: demoAmlCases, summary: { total_cases: 2, by_status: { open: 1, investigating: 1 }, by_severity: { high: 1, medium: 1 } } });
  const cases = data?.cases || [];
  const summary = data?.summary || {};
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState("investigating");
  const [resolution, setResolution] = useState("");
  const [actionError, setActionError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const customerName = (id) => fullName(demoCustomers.find((item) => item.id === id));
  const visibleCases = cases.filter((item) => statusFilter === "all" || item.status === statusFilter);
  async function saveCase(event) {
    event.preventDefault();
    try {
      const updated = isDemo ? { ...selected, status, resolution } : (await riskService.updateAmlCase(selected.id, { status, resolution: resolution || null })).data;
      setData({ ...data, cases: cases.map((item) => item.id === selected.id ? updated : item) });
      setSelected(null);
    } catch (requestError) {
      setActionError(requestError.response?.data?.detail || "Unable to update case.");
    }
  }
  const columns = useMemo(() => [
    { key: "case_number", label: "Case ID", render: (row) => <strong className="mono">{row.case_number}</strong> },
    { key: "customer_id", label: "Customer", render: (row) => customerName(row.customer_id) },
    { key: "rule_code", label: "Detection rule", render: (row) => <span className="mono">{row.rule_code}</span> },
    { key: "severity", label: "Risk", render: (row) => <StatusBadge value={row.severity} /> },
    { key: "status", label: "Investigation", render: (row) => <StatusBadge value={row.status} /> },
    { key: "created_at", label: "Created", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "action", label: "", render: (row) => <button className="button button-quiet" onClick={(event) => { event.stopPropagation(); setSelected(row); setStatus(row.status === "open" ? "investigating" : row.status); }}>Review case</button> },
  ], []);
  return <div className="page-stack">
    <PageHeader eyebrow="FINANCIAL CRIME COMPLIANCE" title="AML & compliance" description="Monitor traceable alerts and coordinate human-led investigations." />
    {isDemo && <div className="demo-notice"><AlertTriangle size={16} /> AML cases shown are illustrative. Demo data is not evidence of suspicious or illegal activity.</div>}
    <div className="metric-grid four">
      <MetricCard title="Compliance cases" value={summary.total_cases ?? cases.length} note="in current report" icon={FileSearch} tone="blue" />
      <MetricCard title="Open" value={summary.by_status?.open ?? cases.filter((item) => item.status === "open").length} note="awaiting assignment" icon={AlertTriangle} tone="amber" />
      <MetricCard title="Investigating" value={summary.by_status?.investigating ?? cases.filter((item) => item.status === "investigating").length} note="active reviews" icon={Scale} tone="purple" />
      <MetricCard title="Critical alerts" value={summary.by_severity?.critical || 0} note="prioritized for compliance" icon={ShieldCheck} tone="teal" />
    </div>
    <Panel title="AML case queue" description="Case details and status changes are subject to compliance role permissions">
      <DataTable columns={columns} rows={visibleCases} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search case, customer or rule…" emptyText="No AML cases are available." toolbar={<select className="table-select" aria-label="Filter AML case status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All investigation states</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="escalated">Escalated</option><option value="closed">Closed</option></select>} />
    </Panel>
    <Modal open={Boolean(selected)} title="Compliance case review" onClose={() => { setSelected(null); setActionError(""); }}>
      {selected && <form className="form-grid" onSubmit={saveCase}>
        <div className="alert-detail-head full"><div><strong>{selected.case_number}</strong><small>{customerName(selected.customer_id)} · Rule {selected.rule_code}</small></div><StatusBadge value={selected.severity} /></div>
        <div className="detail-grid full"><div><small>Transaction reference</small><strong className="mono">{selected.transaction_id}</strong></div><div><small>Created</small><strong>{new Date(selected.created_at).toLocaleString()}</strong></div></div>
        <label className="field full"><span>Investigation status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="investigating">Investigating</option><option value="escalated">Escalated</option><option value="closed">Closed</option></select></label>
        <label className="field full"><span>Resolution / investigator notes</span><textarea rows={4} maxLength={2000} value={resolution} onChange={(event) => setResolution(event.target.value)} /></label>
        {actionError && <p className="form-error full">{actionError}</p>}
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setSelected(null)}>Cancel</button><button className="button button-primary">Save case update</button></div>
      </form>}
    </Modal>
  </div>;
}
