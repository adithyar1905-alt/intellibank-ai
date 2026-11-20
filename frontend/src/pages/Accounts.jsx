import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleAlert, Eye, Plus, Shield, WalletCards } from "lucide-react";
import { accountService } from "../services/banking.js";
import { demoAccounts, demoCustomers, demoTransactions, formatMoney, fullName } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";

export default function Accounts() {
  const { isDemo } = useAuth();
  const load = useCallback(() => accountService.list({ limit: 100 }), []);
  const { data, setData, loading, error, refresh } = useApiResource(load, demoAccounts);
  const accounts = Array.isArray(data) ? data : [];
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: "", account_type: "savings", currency: "USD" });
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] = useState("");
  const [statement, setStatement] = useState([]);
  const [statementError, setStatementError] = useState("");
  const [statementLoading, setStatementLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const customerName = (id) => fullName(demoCustomers.find((item) => item.id === id));

  useEffect(() => {
    if (!selected) return;
    if (isDemo) {
      setStatement(demoTransactions.filter((item) => item.account_id === selected.id));
      setStatementError("");
      return;
    }
    setStatementLoading(true);
    accountService.statement(selected.id, { limit: 25 })
      .then(({ data: result }) => { setStatement(result.entries || []); setStatementError(""); })
      .catch((requestError) => setStatementError(requestError.response?.data?.detail || "Unable to load account statement."))
      .finally(() => setStatementLoading(false));
  }, [selected, isDemo]);
  const columns = useMemo(() => [
    { key: "account_number_last4", label: "Account", render: (row) => <strong className="mono">•••• {row.account_number_last4}</strong> },
    { key: "customer_id", label: "Customer", render: (row) => <span>{customerName(row.customer_id)}</span> },
    { key: "account_type", label: "Type", render: (row) => <span className="capitalize">{String(row.account_type).replaceAll("_", " ")}</span> },
    { key: "current_balance", label: "Available balance", render: (row) => <strong>{formatMoney(row.available_balance ?? row.current_balance, row.currency)}</strong> },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "created_at", label: "Opened", render: (row) => new Date(row.created_at).toLocaleDateString() },
    { key: "actions", label: "", render: (row) => <div className="row-actions">
      <button className="icon-button" aria-label="View account" onClick={(event) => { event.stopPropagation(); setStatement([]); setSelected(row); }}><Eye size={17} /></button>
      {row.status === "active" ? <button className="icon-button" title="Freeze account" onClick={(event) => { event.stopPropagation(); changeStatus(row, "freeze"); }}><Shield size={16} /></button> : row.status === "frozen" ? <button className="icon-button" title="Unfreeze account" onClick={(event) => { event.stopPropagation(); changeStatus(row, "unfreeze"); }}><Shield size={16} /></button> : null}
      {row.status === "pending_approval" && <button className="button button-quiet" onClick={(event) => { event.stopPropagation(); changeStatus(row, "approve"); }}>Approve</button>}
      {row.status === "pending_activation" && <button className="button button-quiet" onClick={(event) => { event.stopPropagation(); changeStatus(row, "activate"); }}>Activate</button>}
    </div> },
  ], [accounts]);

  async function changeStatus(account, action) {
    setActionError("");
    try {
      if (isDemo) setData(accounts.map((item) => item.id === account.id ? { ...item, status: action === "freeze" ? "frozen" : action === "approve" ? "pending_activation" : "active" } : item));
      else {
        const response = action === "freeze" ? await accountService.freeze(account.id)
          : action === "unfreeze" ? await accountService.unfreeze(account.id)
            : action === "approve" ? await accountService.approve(account.id)
              : await accountService.activate(account.id);
        setData(accounts.map((item) => item.id === account.id ? response.data : item));
      }
    } catch {
      setActionError("Account status could not be changed. Verify your permissions and retry.");
    }
  }

  async function createAccount(event) {
    event.preventDefault();
    setFormError("");
    try {
      if (isDemo) setData([{ ...form, id: `ACC-${Date.now()}`, account_number_last4: String(Date.now()).slice(-4), current_balance: 0, available_balance: 0, status: "pending_approval", created_at: new Date().toISOString() }, ...accounts]);
      else {
        const { data: account } = await accountService.create(form);
        setData([account, ...accounts]);
      }
      setOpen(false);
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to open account.");
    }
  }
  const totalBalance = accounts.reduce((sum, item) => sum + Number(item.current_balance || 0), 0);
  const visibleAccounts = accounts.filter((account) =>
    (statusFilter === "all" || account.status === statusFilter)
    && (typeFilter === "all" || account.account_type === typeFilter),
  );
  return <div className="page-stack">
    <PageHeader eyebrow="DEPOSIT OPERATIONS" title="Account management" description="Review account balances, status, and customer relationships." action={<button className="button button-primary" onClick={() => setOpen(true)}><Plus size={17} /> Open account</button>} />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Account records and controls are illustrative in demo mode.</div>}
    <div className="metric-grid three">
      <MetricCard title="Total accounts" value={accounts.length} note="across account types" icon={WalletCards} tone="blue" />
      <MetricCard title="Total balances" value={formatMoney(totalBalance)} note="displayed account balances" icon={WalletCards} tone="teal" />
      <MetricCard title="Needs attention" value={accounts.filter((item) => ["pending_approval", "frozen"].includes(item.status)).length} note="pending or frozen" icon={Shield} tone="amber" />
    </div>
    <Panel title="Account directory" description="Search by account, customer, type, or status">
      {actionError && <p className="form-error">{actionError}</p>}
      <DataTable columns={columns} rows={visibleAccounts} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search accounts…" emptyText="No accounts are available." toolbar={<><select className="table-select" aria-label="Filter account status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="pending_approval">Pending approval</option><option value="pending_activation">Pending activation</option><option value="active">Active</option><option value="frozen">Frozen</option><option value="closed">Closed</option></select><select className="table-select" aria-label="Filter account type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All account types</option><option value="savings">Savings</option><option value="current">Current</option><option value="fixed_deposit">Fixed deposit</option><option value="recurring_deposit">Recurring deposit</option></select></>} />
    </Panel>
    <Modal open={open} title="Open a bank account" onClose={() => setOpen(false)}>
      <form className="form-grid" onSubmit={createAccount}>
        <label className="field full"><span>Customer ID</span><input required value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })} placeholder="Customer UUID" /></label>
        <label className="field"><span>Account type</span><select value={form.account_type} onChange={(event) => setForm({ ...form, account_type: event.target.value })}><option value="savings">Savings</option><option value="current">Current</option><option value="fixed_deposit">Fixed deposit</option><option value="recurring_deposit">Recurring deposit</option></select></label>
        <label className="field"><span>Currency</span><input maxLength={3} pattern="[A-Za-z]{3}" required value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
        {formError && <p className="form-error full">{formError}</p>}
        <p className="form-hint full">New accounts may require approval or activation. The account number is generated by the backend.</p>
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setOpen(false)}>Cancel</button><button className="button button-primary">Submit application</button></div>
      </form>
    </Modal>
    <Modal open={Boolean(selected)} title="Account details" onClose={() => setSelected(null)}>
      {selected && <div className="profile-detail"><div className="account-number-large">•••• •••• •••• {selected.account_number_last4}</div><div className="detail-grid">
        <div><small>Customer</small><strong>{customerName(selected.customer_id)}</strong></div><div><small>Account type</small><strong className="capitalize">{String(selected.account_type).replaceAll("_", " ")}</strong></div>
        <div><small>Balance</small><strong>{formatMoney(selected.current_balance, selected.currency)}</strong></div><div><small>Status</small><StatusBadge value={selected.status} /></div>
        <div><small>Opened</small><strong>{new Date(selected.created_at).toLocaleDateString()}</strong></div><div><small>Account ID</small><strong className="mono">{selected.id}</strong></div>
      </div>      <div className="detail-section"><h4>Account transaction history</h4>{statementLoading && <p className="subtle-empty">Loading statement…</p>}{statementError && <p className="form-error">{statementError}</p>}{statement.length ? statement.map((entry) => <div className="compact-row" key={entry.transaction_id || entry.id}><span className="compact-copy"><strong>{entry.reference}</strong><small className="capitalize">{entry.transaction_type} · {new Date(entry.created_at).toLocaleString()}</small></span><strong>{formatMoney(entry.amount, entry.currency)}</strong><StatusBadge value={entry.status} /></div>) : !statementLoading && !statementError && <p className="subtle-empty">No account transactions found.</p>}</div></div>}
    </Modal>
  </div>;
}
