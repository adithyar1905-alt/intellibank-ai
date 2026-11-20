import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleAlert, Eye, Pencil, Plus, UserRound, UserRoundPen, Upload } from "lucide-react";
import { customerService } from "../services/banking.js";
import { demoCustomers, fullName } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";

export default function Customers() {
  const { isDemo } = useAuth();
  const load = useCallback(() => customerService.list({ limit: 100 }), []);
  const { data: customers, setData, loading, error, refresh } = useApiResource(load, demoCustomers);
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", phone_number: "" });
  const [formOpen, setFormOpen] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState({ user_id: "", first_name: "", last_name: "", date_of_birth: "" });
  const [history, setHistory] = useState([]);
  const [riskProfile, setRiskProfile] = useState(null);
  const [historyError, setHistoryError] = useState("");
  const [documentType, setDocumentType] = useState("Identity document");
  const [documentFile, setDocumentFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [kycFilter, setKycFilter] = useState("all");
  const safeCustomers = Array.isArray(customers) ? customers : [];

  useEffect(() => {
    if (!selected || isDemo) {
      setHistory([]);
      setRiskProfile(null);
      setHistoryError("");
      return;
    }
    Promise.all([
      customerService.accountHistory(selected.id, { limit: 10 }),
      customerService.riskProfile(selected.id),
    ])
      .then(([historyResponse, riskResponse]) => {
        setHistory(historyResponse.data);
        setRiskProfile(riskResponse.data);
        setHistoryError("");
      })
      .catch((requestError) => setHistoryError(requestError.response?.data?.detail || "Unable to load customer risk or transaction information."));
  }, [selected, isDemo]);

  const columns = useMemo(() => [
    { key: "customer_number", label: "Customer ID", render: (row) => <strong className="mono">{row.customer_number || String(row.id).slice(0, 12)}</strong> },
    { key: "name", label: "Customer", searchValue: (row) => `${fullName(row)} ${row.email}`, render: (row) => <div className="table-person"><span className="avatar avatar-small">{row.first_name?.[0]}{row.last_name?.[0]}</span><span><strong>{fullName(row)}</strong><small>{row.email}</small></span></div> },
    { key: "phone_number", label: "Phone" },
    { key: "status", label: "Account status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "kyc_status", label: "KYC", render: (row) => <StatusBadge value={row.kyc_status} /> },
    { key: "created_at", label: "Registered", render: (row) => new Date(row.created_at).toLocaleDateString() },
    { key: "action", label: "", render: (row) => <button className="icon-button" aria-label={`View ${fullName(row)}`} onClick={(event) => { event.stopPropagation(); setSelected(row); }}><Eye size={17} /></button> },
  ], []);

  async function submitCustomer(event) {
    event.preventDefault();
    setFormError("");
    try {
      if (isDemo) {
        const newCustomer = { ...form, id: `CUS-${Date.now()}`, customer_number: `CUS-${Date.now()}`, email: "demo.customer@example.com", status: "active", kyc_status: "not_submitted", created_at: new Date().toISOString(), kyc_documents: [] };
        setData([newCustomer, ...safeCustomers]);
      } else {
        const { data } = await customerService.create({ ...form, date_of_birth: form.date_of_birth || null });
        setData([data, ...safeCustomers]);
      }
      setFormOpen(false);
      setForm({ user_id: "", first_name: "", last_name: "", date_of_birth: "" });
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to create customer. Check the user ID and fields.");
    }
  }

  async function uploadKyc(event) {
    event.preventDefault();
    if (!selected || !documentFile) return;
    setBusy(true);
    setFormError("");
    try {
      let document;
      if (isDemo) {
        document = { id: `DOC-${Date.now()}`, document_type: documentType, status: "pending", created_at: new Date().toISOString() };
      } else {
        document = (await customerService.uploadKyc(selected.id, documentType, documentFile)).data;
      }
      const updated = { ...selected, kyc_status: "pending", kyc_documents: [...(selected.kyc_documents || []), document] };
      setSelected(updated);
      setData(safeCustomers.map((item) => item.id === selected.id ? updated : item));
      setDocumentFile(null);
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Document upload failed. Check file type and size.");
    } finally { setBusy(false); }
  }

  async function changeCustomerStatus(status) {
    if (!selected) return;
    setBusy(true);
    setFormError("");
    try {
      const updated = isDemo
        ? { ...selected, status }
        : status === "inactive" ? (await customerService.deactivate(selected.id)).data : (await customerService.setStatus(selected.id, status)).data;
      setSelected(updated);
      setData(safeCustomers.map((item) => item.id === selected.id ? updated : item));
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to update customer status.");
    } finally { setBusy(false); }
  }

  async function reviewDocument(documentId, status) {
    if (!selected) return;
    setBusy(true);
    setFormError("");
    try {
      const document = isDemo
        ? { ...selected.kyc_documents.find((item) => item.id === documentId), status }
        : (await customerService.reviewKyc(selected.id, documentId, status)).data;
      const updated = {
        ...selected,
        kyc_documents: selected.kyc_documents.map((item) => item.id === documentId ? document : item),
      };
      setSelected(updated);
      setData(safeCustomers.map((item) => item.id === selected.id ? updated : item));
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to review this KYC document.");
    } finally { setBusy(false); }
  }

  async function saveCustomer(event) {
    event.preventDefault();
    if (!selected) return;
    setFormError("");
    try {
      const patch = Object.fromEntries(Object.entries(editForm).filter(([, value]) => value.trim()));
      const updated = isDemo
        ? { ...selected, ...patch }
        : (await customerService.update(selected.id, patch)).data;
      setSelected(updated);
      setData(safeCustomers.map((item) => item.id === selected.id ? updated : item));
      setEditing(false);
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to update customer profile.");
    }
  }

  const verified = safeCustomers.filter((customer) => customer.kyc_status === "verified").length;
  const visibleCustomers = safeCustomers.filter((customer) =>
    (statusFilter === "all" || customer.status === statusFilter)
    && (kycFilter === "all" || customer.kyc_status === kycFilter),
  );
  return <div className="page-stack">
    <PageHeader eyebrow="CUSTOMER OPERATIONS" title="Customer management" description="Manage customer profiles, onboarding status, and KYC readiness." action={<button className="button button-primary" onClick={() => setFormOpen(true)}><Plus size={17} /> Add customer</button>} />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Customer directory is illustrative until connected to an authenticated backend session.</div>}
    <div className="metric-grid three">
      <MetricCard title="Total customers" value={safeCustomers.length} note="in current directory" icon={UserRound} tone="blue" />
      <MetricCard title="KYC verified" value={verified} note={`${safeCustomers.length ? Math.round(verified / safeCustomers.length * 100) : 0}% of displayed customers`} icon={UserRoundPen} tone="teal" />
      <MetricCard title="KYC pending" value={safeCustomers.filter((customer) => ["pending", "not_submitted"].includes(customer.kyc_status)).length} note="awaiting document review" icon={CircleAlert} tone="amber" />
    </div>
    <Panel title="Customer directory" description="Search and manage customer records">
      <DataTable columns={columns} rows={visibleCustomers} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search name, email or customer ID…" emptyText="No customers have been added yet." toolbar={<><select className="table-select" aria-label="Filter customer status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="blocked">Blocked</option></select><select className="table-select" aria-label="Filter KYC status" value={kycFilter} onChange={(event) => setKycFilter(event.target.value)}><option value="all">All KYC</option><option value="verified">Verified</option><option value="pending">Pending</option><option value="rejected">Rejected</option><option value="not_submitted">Not submitted</option></select></>} />
    </Panel>

    <Modal open={formOpen} title="Add customer profile" onClose={() => setFormOpen(false)}>
      <form className="form-grid" onSubmit={submitCustomer}>
        <label className="field full"><span>Existing user ID <i>Required by the customer API</i></span><input required value={form.user_id} onChange={(event) => setForm({ ...form, user_id: event.target.value })} placeholder="UUID from authenticated user record" /></label>
        <label className="field"><span>First name</span><input required maxLength={100} value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label>
        <label className="field"><span>Last name</span><input required maxLength={100} value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label>
        <label className="field full"><span>Date of birth</span><input type="date" value={form.date_of_birth} onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })} /></label>
        {formError && <p className="form-error full">{formError}</p>}
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setFormOpen(false)}>Cancel</button><button className="button button-primary">Create customer</button></div>
      </form>
    </Modal>
    <Modal open={Boolean(selected)} title="Customer profile" onClose={() => { setSelected(null); setFormError(""); setEditing(false); }}>
      {selected && <div className="profile-detail">
        <div className="profile-detail-head"><span className="avatar avatar-large">{selected.first_name?.[0]}{selected.last_name?.[0]}</span><span className="profile-detail-name"><h3>{fullName(selected)}</h3><span>{selected.email}</span></span><button className="button button-outline" onClick={() => { setEditForm({ first_name: selected.first_name || "", last_name: selected.last_name || "", email: selected.email || "", phone_number: selected.phone_number || "" }); setEditing(true); }}><Pencil size={14} /> Edit</button></div>
        <div className="detail-grid"><div><small>Customer ID</small><strong>{selected.customer_number}</strong></div><div><small>Phone</small><strong>{selected.phone_number || "—"}</strong></div><div><small>Account status</small><StatusBadge value={selected.status} /></div><div><small>KYC verification</small><StatusBadge value={selected.kyc_status} /></div><div><small>Registration date</small><strong>{new Date(selected.created_at).toLocaleDateString()}</strong></div></div>
        <div className="detail-section"><h4>KYC documents</h4>{selected.kyc_documents?.length ? selected.kyc_documents.map((doc) => <div className="compact-row" key={doc.id}><span className="compact-copy"><strong>{doc.document_type}</strong><small>Added {new Date(doc.created_at).toLocaleDateString()}</small></span><StatusBadge value={doc.status} />{!isDemo && doc.status === "pending" && <><button disabled={busy} className="button button-quiet" onClick={() => reviewDocument(doc.id, "verified")}>Verify</button><button disabled={busy} className="button button-quiet danger-text" onClick={() => reviewDocument(doc.id, "rejected")}>Reject</button></>}</div>) : <div className="subtle-empty">No document details are available for this profile.</div>}</div>
        <form className="kyc-upload-form" onSubmit={uploadKyc}>
          <label className="field"><span>Document type</span><input required maxLength={40} value={documentType} onChange={(event) => setDocumentType(event.target.value)} /></label>
          <label className="field"><span>Secure document upload</span><input required type="file" accept="image/jpeg,image/png,application/pdf" onChange={(event) => setDocumentFile(event.target.files?.[0] || null)} /></label>
          <button className="button button-outline" disabled={busy || !documentFile}><Upload size={15} /> Upload KYC document</button>
        </form>
        {formError && <p className="form-error">{formError}</p>}
        <div className="detail-section"><h4>Customer risk profile</h4>{riskProfile ? <div className="compact-row"><strong>{Math.round(Number(riskProfile.risk_score) * 100)}% risk signal</strong><StatusBadge value={riskProfile.risk_level} /><span>{riskProfile.open_alert_count} open alerts</span></div> : <p className="subtle-empty">{isDemo ? "Illustrative risk information is available in Fraud Detection." : historyError ? "Risk profile unavailable." : "No risk profile returned."}</p>}</div>
        <div className="detail-section"><h4>Recent account transactions</h4>{historyError && <p className="form-error">{historyError}</p>}{isDemo ? <p className="subtle-empty">Demo history is available in the Transactions module.</p> : history.length ? history.map((entry) => <div className="compact-row" key={entry.transaction_id}><span className="compact-copy"><strong>{entry.reference}</strong><small>{entry.transaction_type} · •••• {entry.account_number_last4}</small></span><strong>{entry.currency} {entry.amount}</strong><StatusBadge value={entry.status} /></div>) : <p className="subtle-empty">{historyError ? "Transaction history unavailable." : "No account transaction history found."}</p>}</div>
        {!isDemo && <div className="form-actions"><button disabled={busy || selected.status === "inactive"} className="button button-outline danger-outline" onClick={() => changeCustomerStatus("inactive")}>Deactivate customer</button><button disabled={busy || selected.status === "active"} className="button button-outline" onClick={() => changeCustomerStatus("active")}>Set active</button></div>}
      </div>}
    </Modal>
    <Modal open={editing} title="Edit customer profile" onClose={() => setEditing(false)}>
      <form className="form-grid" onSubmit={saveCustomer}>
        <label className="field"><span>First name</span><input required maxLength={100} value={editForm.first_name} onChange={(event) => setEditForm({ ...editForm, first_name: event.target.value })} /></label>
        <label className="field"><span>Last name</span><input required maxLength={100} value={editForm.last_name} onChange={(event) => setEditForm({ ...editForm, last_name: event.target.value })} /></label>
        <label className="field"><span>Email address</span><input type="email" required value={editForm.email} onChange={(event) => setEditForm({ ...editForm, email: event.target.value })} /></label>
        <label className="field"><span>Phone number</span><input minLength={7} maxLength={32} value={editForm.phone_number} onChange={(event) => setEditForm({ ...editForm, phone_number: event.target.value })} /></label>
        {formError && <p className="form-error full">{formError}</p>}
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setEditing(false)}>Cancel</button><button className="button button-primary">Save changes</button></div>
      </form>
    </Modal>
  </div>;
}
