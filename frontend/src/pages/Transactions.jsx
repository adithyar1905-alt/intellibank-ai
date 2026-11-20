import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, CircleAlert, Plus, ReceiptText } from "lucide-react";
import { accountService, transactionService } from "../services/banking.js";
import { demoAccounts, demoTransactions, formatMoney } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Modal from "../components/Modal.jsx";

const demoTransactionData = { accounts: demoAccounts, transactions: demoTransactions };

export default function Transactions() {
  const { isDemo } = useAuth();
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const load = useCallback(async () => {
    const { data: accounts } = await accountService.list({ limit: 100 });
    const accountId = selectedAccountId || accounts[0]?.id;
    const { data: transactions } = accountId
      ? await transactionService.list(accountId, { limit: 100 })
      : { data: [] };
    return { accounts, transactions };
  }, [selectedAccountId]);
  const { data, setData, loading, error, refresh } = useApiResource(load, demoTransactionData);
  const accounts = data?.accounts || [];
  const transactions = data?.transactions || [];
  const [open, setOpen] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [form, setForm] = useState({ account_id: "", related_account_id: "", transaction_type: "deposit", amount: "", counterparty_reference: "", description: "" });
  const [formError, setFormError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    if (!isDemo && !selectedAccountId && accounts[0]?.id) setSelectedAccountId(accounts[0].id);
  }, [accounts, isDemo, selectedAccountId]);
  useEffect(() => {
    if (!isDemo && selectedAccountId) refresh().catch(() => {});
  }, [isDemo, refresh, selectedAccountId]);

  const columns = useMemo(() => [
    { key: "reference", label: "Transaction ID", render: (row) => <strong className="mono">{row.reference}</strong> },
    { key: "account_id", label: "Account", render: (row) => <span className="mono">•••• {accounts.find((account) => account.id === row.account_id)?.account_number_last4 || String(row.account_id).slice(-4)}</span> },
    { key: "transaction_type", label: "Type", render: (row) => <span className="capitalize">{row.transaction_type}</span> },
    { key: "amount", label: "Amount", render: (row) => <strong>{formatMoney(row.amount, row.currency)}</strong> },
    { key: "created_at", label: "Date", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", label: "", render: (row) => <button className="icon-button" aria-label="View receipt" onClick={(event) => { event.stopPropagation(); viewReceipt(row); }}><ReceiptText size={17} /></button> },
  ], [accounts]);

  async function viewReceipt(row) {
    if (isDemo) setReceipt(row);
    else {
      try { setReceipt((await transactionService.receipt(row.id)).data); }
      catch (requestError) { setFormError(requestError.response?.data?.detail || "Unable to load transaction receipt."); setOpen(true); }
    }
  }
  async function createTransaction(event) {
    event.preventDefault();
    setFormError("");
    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) { setFormError("Enter an amount greater than zero."); return; }
    if (!isDemo) {
      setFormError("Transaction initiation is disabled in this frontend. Use your bank’s approved transaction workflow.");
      return;
    }
    try {
      const transaction = { ...form, id: `TXN-${Date.now()}`, reference: `IB-DEMO-${Date.now()}`, amount, currency: accounts.find((item) => item.id === form.account_id)?.currency || "USD", status: "completed", created_at: new Date().toISOString() };
      setData({ ...data, transactions: [transaction, ...transactions] });
      setOpen(false);
    } catch (requestError) {
      setFormError(requestError.response?.data?.detail || "Unable to create transaction.");
    }
  }

  const reviewCount = transactions.filter((item) => item.status === "review_required").length;
  const totalVolume = transactions.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const visibleTransactions = transactions.filter((item) =>
    (!selectedAccountId || item.account_id === selectedAccountId)
    &&
    (statusFilter === "all" || item.status === statusFilter)
    && (typeFilter === "all" || item.transaction_type === typeFilter),
  );
  return <div className="page-stack">
    <PageHeader eyebrow="BANKING OPERATIONS" title="Transactions" description="Monitor deposits, withdrawals, transfers, and payment-rail activity." action={isDemo ? <button className="button button-primary" onClick={() => setOpen(true)}><Plus size={17} /> Add demo transaction</button> : <span className="read-only-label">Read-only transaction monitoring</span>} />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Demo entries are simulated; no money movement is performed in this interface.</div>}
    <div className="metric-grid three">
      <MetricCard title="Transactions shown" value={transactions.length} note="in current data window" icon={Activity} tone="blue" />
      <MetricCard title="Displayed volume" value={formatMoney(totalVolume)} note="transaction amount sum" icon={ReceiptText} tone="teal" />
      <MetricCard title="Needs review" value={reviewCount} note="human review required" icon={CircleAlert} tone="amber" />
    </div>
    <Panel title="Transaction activity" description="Filter by transaction ID, type, account, or status">
      <DataTable columns={columns} rows={visibleTransactions} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search transactions…" emptyText="No transaction activity is available." toolbar={<><select className="table-select" aria-label="Filter account" value={selectedAccountId} onChange={(event) => { setSelectedAccountId(event.target.value); if (isDemo) setData({ ...data, transactions: event.target.value ? demoTransactions.filter((item) => item.account_id === event.target.value) : demoTransactions }); }}><option value="">All demo accounts</option>{accounts.map((account) => <option key={account.id} value={account.id}>•••• {account.account_number_last4}</option>)}</select><select className="table-select" aria-label="Filter transaction status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{["completed", "pending", "review_required", "failed", "reversed", "rejected"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select><select className="table-select" aria-label="Filter transaction type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All types</option>{["deposit", "withdrawal", "transfer", "neft", "rtgs", "imps", "upi"].map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></>} />
    </Panel>
    <Modal open={open} title="Create transaction" onClose={() => setOpen(false)}>
      <form className="form-grid" onSubmit={createTransaction}>
        <label className="field full"><span>Source account</span><select required value={form.account_id} onChange={(event) => setForm({ ...form, account_id: event.target.value })}><option value="">Choose account</option>{accounts.map((account) => <option key={account.id} value={account.id}>•••• {account.account_number_last4} · {account.status}</option>)}</select></label>
        <label className="field"><span>Type</span><select value={form.transaction_type} onChange={(event) => setForm({ ...form, transaction_type: event.target.value })}><option value="deposit">Deposit</option><option value="withdrawal">Withdrawal</option><option value="transfer">Internal transfer</option><option value="neft">NEFT</option><option value="rtgs">RTGS</option><option value="imps">IMPS</option><option value="upi">UPI</option></select></label>
        <label className="field"><span>Amount</span><input type="number" min="0.01" step="0.01" required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
        {form.transaction_type === "transfer" && <label className="field full"><span>Destination account</span><select required value={form.related_account_id} onChange={(event) => setForm({ ...form, related_account_id: event.target.value })}><option value="">Choose destination</option>{accounts.filter((account) => account.id !== form.account_id).map((account) => <option key={account.id} value={account.id}>•••• {account.account_number_last4}</option>)}</select></label>}
        {["neft", "rtgs", "imps", "upi"].includes(form.transaction_type) && <label className="field full"><span>Beneficiary reference</span><input required minLength={4} maxLength={64} value={form.counterparty_reference} onChange={(event) => setForm({ ...form, counterparty_reference: event.target.value })} placeholder="Verified beneficiary reference" /></label>}
        <label className="field full"><span>Description</span><input maxLength={255} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        {formError && <p className="form-error full">{formError}</p>}
        <p className="form-hint full">Demo mode only creates a local illustrative row. Transaction initiation is intentionally disabled for connected sessions.</p>
        <div className="form-actions full"><button type="button" className="button button-outline" onClick={() => setOpen(false)}>Cancel</button><button className="button button-primary">Submit</button></div>
      </form>
    </Modal>
    <Modal open={Boolean(receipt)} title="Transaction receipt" onClose={() => setReceipt(null)}>
      {receipt && <div className="profile-detail"><div className="receipt-mark"><ReceiptText size={21} /></div><div className="account-number-large">{receipt.reference}</div><div className="detail-grid">
        <div><small>Type</small><strong className="capitalize">{receipt.transaction_type}</strong></div><div><small>Amount</small><strong>{formatMoney(receipt.amount, receipt.currency)}</strong></div>
        <div><small>Status</small><StatusBadge value={receipt.status} /></div><div><small>Date</small><strong>{new Date(receipt.created_at).toLocaleString()}</strong></div>
      </div></div>}
    </Modal>
  </div>;
}
