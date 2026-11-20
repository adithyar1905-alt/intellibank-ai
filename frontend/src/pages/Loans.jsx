import { useCallback, useMemo, useState } from "react";
import { BadgeDollarSign, CircleAlert, Eye, FileCheck2, XCircle } from "lucide-react";
import { loanService } from "../services/banking.js";
import { demoApplications, demoCustomers, formatMoney, fullName } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";

export default function Loans() {
  const { isDemo } = useAuth();
  const load = useCallback(() => loanService.applications({ limit: 100 }), []);
  const { data, setData, loading, error, refresh } = useApiResource(load, demoApplications);
  const applications = Array.isArray(data) ? data : [];
  const [selected, setSelected] = useState(null);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const customerName = (id) => fullName(demoCustomers.find((item) => item.id === id));
  async function updateApplication(application, action) {
    setActionError("");
    try {
      let result;
      if (isDemo) result = { ...application, status: action === "approve" ? "approved" : "rejected" };
      else {
        const response = action === "approve"
          ? await loanService.approve(application.id)
          : await loanService.reject(application.id, reason);
        result = action === "approve" ? { ...application, ...response.data, status: "approved" } : response.data;
      }
      setData(applications.map((item) => item.id === application.id ? result : item));
      setSelected(null);
      setRejecting(null);
      setReason("");
    } catch (requestError) {
      setActionError(requestError.response?.data?.detail || "Unable to update this loan application.");
    }
  }
  const columns = useMemo(() => [
    { key: "id", label: "Application ID", render: (row) => <strong className="mono">{row.id}</strong> },
    { key: "customer_id", label: "Applicant", render: (row) => <span>{customerName(row.customer_id)}</span> },
    { key: "loan_type", label: "Loan type", render: (row) => <span className="capitalize">{row.loan_type}</span> },
    { key: "requested_amount", label: "Amount", render: (row) => <strong>{formatMoney(row.requested_amount)}</strong> },
    { key: "requested_term_months", label: "Term", render: (row) => `${row.requested_term_months} months` },
    { key: "submitted_at", label: "Submitted", render: (row) => new Date(row.submitted_at).toLocaleDateString() },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "", render: (row) => <button className="icon-button" aria-label="Review application" onClick={(event) => { event.stopPropagation(); setSelected(row); }}><Eye size={17} /></button> },
  ], []);
  const count = (status) => applications.filter((item) => item.status === status).length;
  const visibleApplications = applications.filter((item) => statusFilter === "all" || item.status === statusFilter);
  return <div className="page-stack">
    <PageHeader eyebrow="CREDIT OPERATIONS" title="Loan management" description="Review applications, monitor decisions, and track loan pipeline status." />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Loan pipeline is illustrative in demo mode. Approval and rejection controls only update demo state.</div>}
    <div className="metric-grid four">
      <MetricCard title="Applications" value={applications.length} note="total in current view" icon={BadgeDollarSign} tone="blue" />
      <MetricCard title="Pending review" value={count("submitted") + count("under_review")} note="awaiting loan officer" icon={FileCheck2} tone="amber" />
      <MetricCard title="Approved" value={count("approved") + count("disbursed")} note="approved or disbursed" icon={BadgeDollarSign} tone="teal" />
      <MetricCard title="Rejected" value={count("rejected")} note="applications declined" icon={XCircle} tone="purple" />
    </div>
    <Panel title="Loan applications" description="Personal, home, education, vehicle, and business lending">
      <DataTable columns={columns} rows={visibleApplications} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search application, applicant or loan type…" emptyText="No loan applications are available." toolbar={<select className="table-select" aria-label="Filter loan status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All application statuses</option>{["submitted", "under_review", "approved", "rejected", "withdrawn", "disbursed"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select>} />
    </Panel>
    <Modal open={Boolean(selected)} title="Application review" onClose={() => { setSelected(null); setActionError(""); }}>
      {selected && <div className="profile-detail">
        <div className="application-summary"><span className="mini-icon teal"><BadgeDollarSign size={19} /></span><span><h3>{selected.id}</h3><small>{customerName(selected.customer_id)} · <span className="capitalize">{selected.loan_type} loan</span></small></span><StatusBadge value={selected.status} /></div>
        <div className="detail-grid"><div><small>Requested amount</small><strong>{formatMoney(selected.requested_amount)}</strong></div><div><small>Repayment term</small><strong>{selected.requested_term_months} months</strong></div><div><small>Declared monthly income</small><strong>{formatMoney(selected.declared_monthly_income)}</strong></div><div><small>Submitted</small><strong>{new Date(selected.submitted_at).toLocaleString()}</strong></div></div>
        <div className="detail-section"><h4>Submitted documents</h4>{selected.documents?.length ? selected.documents.map((doc) => <div key={doc.id} className="compact-row">{doc.document_type}<StatusBadge value="submitted" /></div>) : <div className="subtle-empty">No documents attached in this view.</div>}</div>
        {actionError && <p className="form-error">{actionError}</p>}
        {["submitted", "under_review"].includes(selected.status) && <div className="form-actions"><button className="button button-outline danger-outline" onClick={() => setRejecting(selected)}>Reject application</button><button className="button button-primary" onClick={() => updateApplication(selected, "approve")}>Approve application</button></div>}
      </div>}
    </Modal>
    <Modal open={Boolean(rejecting)} title="Reject loan application" onClose={() => setRejecting(null)}>
      <form className="form-grid" onSubmit={(event) => { event.preventDefault(); updateApplication(rejecting, "reject"); }}>
        <label className="field full"><span>Reason for rejection</span><textarea required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} rows={4} /></label>
        {actionError && <p className="form-error full">{actionError}</p>}
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setRejecting(null)}>Cancel</button><button className="button button-danger">Confirm rejection</button></div>
      </form>
    </Modal>
  </div>;
}
