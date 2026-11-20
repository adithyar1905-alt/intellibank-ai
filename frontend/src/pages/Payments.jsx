import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleAlert, CreditCard, ExternalLink, RotateCcw } from "lucide-react";
import { accountService, transactionService } from "../services/banking.js";
import { demoAccounts, demoTransactions, formatMoney } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const railTypes = ["upi", "neft", "rtgs", "imps"];
const demoPayments = { accounts: demoAccounts, transactions: demoTransactions.filter((item) => railTypes.includes(item.transaction_type)) };

export default function Payments() {
  const { isDemo } = useAuth();
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const load = useCallback(async () => {
    const { data: accounts } = await accountService.list({ limit: 100 });
    const accountId = selectedAccountId || accounts[0]?.id;
    const { data: transactions } = accountId ? await transactionService.list(accountId, { limit: 100 }) : { data: [] };
    return { accounts, transactions: transactions.filter((item) => railTypes.includes(item.transaction_type)) };
  }, [selectedAccountId]);
  const { data, setData, loading, error, refresh } = useApiResource(load, demoPayments);
  const [statusFilter, setStatusFilter] = useState("all");
  const accounts = data?.accounts || [];
  const payments = data?.transactions || [];
  useEffect(() => {
    if (!isDemo && !selectedAccountId && accounts[0]?.id) setSelectedAccountId(accounts[0].id);
  }, [accounts, isDemo, selectedAccountId]);
  useEffect(() => {
    if (!isDemo && selectedAccountId) refresh().catch(() => {});
  }, [isDemo, refresh, selectedAccountId]);
  const visiblePayments = payments.filter((item) => statusFilter === "all" || item.status === statusFilter);
  const columns = useMemo(() => [
    { key: "reference", label: "Payment reference", render: (row) => <strong className="mono">{row.reference}</strong> },
    { key: "transaction_type", label: "Rail", render: (row) => <span className="rail-chip">{row.transaction_type?.toUpperCase()}</span> },
    { key: "account_id", label: "Account", render: (row) => <span className="mono">•••• {accounts.find((item) => item.id === row.account_id)?.account_number_last4 || String(row.account_id).slice(-4)}</span> },
    { key: "amount", label: "Amount", render: (row) => <strong>{formatMoney(row.amount, row.currency)}</strong> },
    { key: "created_at", label: "Date", render: (row) => new Date(row.created_at).toLocaleString() },
    { key: "status", label: "Payment status", render: (row) => <StatusBadge value={row.status} /> },
  ], [accounts]);
  return <div className="page-stack">
    <PageHeader eyebrow="PAYMENT RAILS" title="Payments" description="Track UPI, NEFT, RTGS, and IMPS payments and failed activity." />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> Payment history is illustrative. Payment initiation is intentionally not implemented in the frontend.</div>}
    <div className="metric-grid three">
      <MetricCard title="Payments shown" value={payments.length} note="payment-rail transactions" icon={CreditCard} tone="blue" />
      <MetricCard title="Completed" value={payments.filter((item) => item.status === "completed").length} note="successful in this data window" icon={ExternalLink} tone="teal" />
      <MetricCard title="Failed payments" value={payments.filter((item) => item.status === "failed").length} note="review retry or beneficiary details" icon={RotateCcw} tone="amber" />
    </div>
    <Panel title="Payment history" description="Payment-rail activity from the transaction service">
      <DataTable columns={columns} rows={visiblePayments} loading={loading} error={error} onRetry={refresh} searchPlaceholder="Search reference, rail or status…" emptyText="No payment-rail transactions found." toolbar={<><select className="table-select" aria-label="Filter account" value={selectedAccountId} onChange={(event) => { setSelectedAccountId(event.target.value); if (isDemo) setData({ ...data, transactions: event.target.value ? demoTransactions.filter((item) => item.account_id === event.target.value && railTypes.includes(item.transaction_type)) : demoPayments.transactions }); }}><option value="">All demo accounts</option>{accounts.map((account) => <option key={account.id} value={account.id}>•••• {account.account_number_last4}</option>)}</select><select className="table-select" aria-label="Filter payment status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="pending">Pending</option><option value="review_required">Review required</option></select></>} />
    </Panel>
    <div className="notice-card"><CircleAlert size={18} /><div><strong>No live payment processing</strong><p>This screen is read-only. Payment initiation and settlement are controlled by the authenticated backend transaction workflow.</p></div></div>
  </div>;
}
