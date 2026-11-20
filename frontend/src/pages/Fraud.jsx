import { useCallback, useMemo, useState } from "react";
import { Activity, CircleAlert, Eye, ShieldAlert, ShieldCheck } from "lucide-react";
import { riskService } from "../services/banking.js";
import { demoFraudAlerts, demoTransactions, formatMoney, fullName, demoCustomers } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";
import { RiskChart } from "../components/Charts.jsx";

export default function Fraud() {
  const { isDemo } = useAuth();
  const load = useCallback(() => riskService.fraudAlerts({ limit: 100 }), []);
  const { data, setData, loading, error, refresh } = useApiResource(load, demoFraudAlerts);
  const alerts = Array.isArray(data) ? data : [];
  const [selected, setSelected] = useState(null);
  const [decision, setDecision] = useState("investigate");
  const [notes, setNotes] = useState("");
  const [actionError, setActionError] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const name = (id) => fullName(demoCustomers.find((item) => item.id === id));

  async function submitReview(event) {
    event.preventDefault();
    try {
      const updated = isDemo
        ? { ...selected, status: decision === "investigate" ? "investigating" : "resolved", details: { ...(selected.details || {}), review: { decision, notes } } }
        : (await riskService.reviewFraud(selected.id, { decision, notes: notes || null })).data;
      setData(alerts.map((item) => item.id === selected.id ? updated : item));
      setSelected(null);
      setNotes("");
      setActionError("");
    } catch (requestError) {
      setActionError(requestError.response?.data?.detail || "Unable to submit the review.");
    }
  }
  const columns = useMemo(() => [
    { key: "transaction_id", label: "Transaction", render: (row) => <strong className="mono">{row.transaction_id || "—"}</strong> },
    { key: "customer_id", label: "Customer", render: (row) => <span>{name(row.customer_id)}</span> },
    { key: "description", label: "Risk signal", render: (row) => <span className="table-description">{row.description}</span> },
    { key: "score", label: "Risk score", render: (row) => <strong className={Number(row.score) >= 0.7 ? "text-danger" : "text-amber"}>{Math.round(Number(row.score) * 100)}%</strong> },
    { key: "severity", label: "Severity", render: (row) => <StatusBadge value={row.severity} /> },
    { key: "status", label: "Investigation", render: (row) => <StatusBadge value={row.status} /> },
    { key: "created_at", label: "Detected", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "actions", label: "", render: (row) => <button className="icon-button" aria-label="Investigate alert" onClick={(event) => { event.stopPropagation(); setSelected(row); }}><Eye size={17} /></button> },
  ], [alerts]);
  const count = (severity) => alerts.filter((item) => item.severity === severity).length;
  const visibleAlerts = alerts.filter((item) =>
    (severityFilter === "all" || item.severity === severityFilter)
    && (statusFilter === "all" || item.status === statusFilter),
  );
  return <div className="page-stack">
    <PageHeader eyebrow="RISK OPERATIONS" title="Fraud detection" description="Investigate risk signals and review suspicious transaction activity." />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Risk scores below are illustrative demo data—not real fraud predictions or determinations.</div>}
    <div className="metric-grid four">
      <MetricCard title="Total alerts" value={alerts.length} note="in current review queue" icon={ShieldAlert} tone="blue" />
      <MetricCard title="High / critical" value={count("high") + count("critical")} note="priority human review" icon={CircleAlert} tone="amber" />
      <MetricCard title="Medium risk" value={count("medium")} note="monitor and investigate" icon={Activity} tone="purple" />
      <MetricCard title="Low risk" value={count("low")} note="monitoring signals" icon={ShieldCheck} tone="teal" />
    </div>
    <div className="grid-two">
      <Panel title="Risk distribution" description="Illustrative classification of queued alerts"><RiskChart data={[
        { name: "Low", value: count("low") || 1 }, { name: "Medium", value: count("medium") || 1 },
        { name: "High", value: count("high") || 1 }, { name: "Critical", value: count("critical") || 1 },
      ]} /><div className="chart-legend"><span><i className="legend-dot teal-dot" /> Low</span><span><i className="legend-dot yellow-dot" /> Medium</span><span><i className="legend-dot orange-dot" /> High</span><span><i className="legend-dot red-dot" /> Critical</span></div></Panel>
      <Panel title="Review guidance" description="Model output is a signal only">
        <div className="guidance-list">
          <div className="guidance-item"><span className="mini-icon danger"><ShieldAlert size={17} /></span><span><strong>Human investigation required</strong><small>Risk scores do not establish fraud or justify an automatic account freeze.</small></span></div>
          <div className="guidance-item"><span className="mini-icon teal"><ShieldCheck size={17} /></span><span><strong>Transactions may be held for review</strong><small>High-risk transaction reviews must follow bank policy and an authorized decision.</small></span></div>
          <div className="guidance-item"><span className="mini-icon blue"><Activity size={17} /></span><span><strong>Illustrative monitoring</strong><small>Demo alerts have no connection to real accounts or production model outputs.</small></span></div>
        </div>
      </Panel>
    </div>
    <Panel title="Suspicious activity queue" description="Open an alert to record an investigation outcome">
      <DataTable columns={columns} rows={visibleAlerts} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search alerts, customer or transaction…" emptyText="No fraud alerts are available." toolbar={<><select className="table-select" aria-label="Filter risk severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="all">All severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><select className="table-select" aria-label="Filter investigation status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All investigation states</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></>} />
    </Panel>
    <Modal open={Boolean(selected)} title="Investigate alert" onClose={() => setSelected(null)}>
      {selected && <form className="form-grid" onSubmit={submitReview}>
        <div className="alert-detail-head full"><div><strong>{selected.description}</strong><small>{selected.transaction_id} · {name(selected.customer_id)}</small></div><StatusBadge value={selected.severity} /></div>
        <div className="detail-grid full"><div><small>Risk score</small><strong>{Math.round(Number(selected.score) * 100)}% <small>illustrative</small></strong></div><div><small>Investigation status</small><StatusBadge value={selected.status} /></div><div><small>Amount context</small><strong>{formatMoney(demoTransactions.find((item) => item.id === selected.transaction_id)?.amount || 0)}</strong></div><div><small>Created</small><strong>{new Date(selected.created_at).toLocaleString()}</strong></div></div>
        <label className="field full"><span>Decision</span><select value={decision} onChange={(event) => setDecision(event.target.value)}><option value="investigate">Continue investigation</option><option value="approve">Approve transaction / resolve</option><option value="reject">Reject transaction / resolve</option></select></label>
        <label className="field full"><span>Investigation notes</span><textarea rows={3} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Document review rationale…" /></label>
        {actionError && <p className="form-error full">{actionError}</p>}
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setSelected(null)}>Cancel</button><button className="button button-primary">Save review</button></div>
      </form>}
    </Modal>
  </div>;
}
