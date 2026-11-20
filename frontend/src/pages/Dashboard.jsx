import { useCallback } from "react";
import { Activity, ArrowRight, BadgeDollarSign, CircleAlert, Landmark, Users, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { accountService, customerService, loanService, transactionService } from "../services/banking.js";
import { demoAccounts, demoApplications, demoCustomers, demoTransactions, formatMoney, fullName, monthlyData } from "../data/demo.js";
import { useApiResource } from "../app/useApiResource.js";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { DepositChart, GrowthChart, VolumeChart } from "../components/Charts.jsx";

const demoDashboard = { customers: demoCustomers, accounts: demoAccounts, transactions: demoTransactions, applications: demoApplications };

export default function Dashboard() {
  const load = useCallback(async () => {
    const [customers, accounts, applications] = await Promise.all([
      customerService.list({ limit: 100 }),
      accountService.list({ limit: 100 }),
      loanService.applications({ limit: 100 }),
    ]);
    let transactions = [];
    if (accounts.data[0]?.id) transactions = (await transactionService.list(accounts.data[0].id, { limit: 100 })).data;
    return { customers: customers.data, accounts: accounts.data, applications: applications.data, transactions };
  }, []);
  const { data = demoDashboard, loading, error, refresh, isDemo } = useApiResource(load, demoDashboard);
  const currentData = data || {};
  const customers = currentData.customers || [];
  const accounts = currentData.accounts || [];
  const transactions = currentData.transactions || [];
  const applications = currentData.applications || [];
  const deposits = accounts.reduce((sum, account) => sum + Number(account.current_balance || 0), 0);

  const transactionColumns = [
    { key: "reference", label: "Reference", render: (row) => <strong className="mono">{row.reference}</strong> },
    { key: "transaction_type", label: "Type", render: (row) => <span className="capitalize">{row.transaction_type}</span> },
    { key: "amount", label: "Amount", render: (row) => <strong>{formatMoney(row.amount, row.currency)}</strong> },
    { key: "created_at", label: "Date", render: (row) => new Date(row.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  ];

  return <div className="page-stack">
    <PageHeader eyebrow="MONDAY, FEBRUARY 18, 2025" title="Good morning, Admin" description="Here’s the latest view of your banking operations." action={<button className="button button-outline" onClick={refresh}><Activity size={16} /> Refresh data</button>} />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> You’re viewing illustrative demo data. Sign in to connect this dashboard to live backend records.</div>}
    <div className="metric-grid four">
      <MetricCard title="Total customers" value={loading ? "—" : customers.length.toLocaleString()} note="registered customers" change="+8.2%" icon={Users} tone="blue" />
      <MetricCard title="Total deposits" value={loading ? "—" : formatMoney(deposits)} note="across displayed accounts" change="+5.4%" icon={Wallet} tone="teal" />
      <MetricCard title="Transactions" value={loading ? "—" : transactions.length.toLocaleString()} note="recent account activity" change="+12.8%" icon={Activity} tone="purple" />
      <MetricCard title="Loan applications" value={loading ? "—" : applications.length.toLocaleString()} note="applications on file" change="+3.1%" icon={BadgeDollarSign} tone="amber" />
    </div>
    {error && <div className="inline-error"><CircleAlert size={17} /> Live dashboard data is incomplete: {error}</div>}
    <div className="grid-two dashboard-charts">
      <Panel title="Transaction volume" description="Monthly processed value · USD millions" action={<Link className="panel-link" to="/analytics">View analytics <ArrowRight size={14} /></Link>}><VolumeChart data={monthlyData} /></Panel>
      <Panel title="Deposits vs. withdrawals" description="Monthly movement · USD millions"><DepositChart data={monthlyData} /></Panel>
    </div>
    <div className="grid-two">
      <Panel title="Recent transactions" description="Latest account activity" action={<Link className="panel-link" to="/transactions">View all <ArrowRight size={14} /></Link>}>
        <DataTable columns={transactionColumns} rows={transactions} loading={loading} error="" onRetry={refresh} pageSize={5} searchPlaceholder="Search recent transactions…" />
      </Panel>
      <Panel title="Customer growth" description="Customer registrations over six months"><GrowthChart data={monthlyData} />
        <div className="insight-strip"><span className="insight-icon"><Landmark size={17} /></span><span><strong>Healthy portfolio growth</strong><small>New registrations are trending steadily upward.</small></span><StatusBadge value="healthy" /></div>
      </Panel>
    </div>
    <div className="grid-two">
      <Panel title="Latest customer registrations" description="Recently onboarded customers" action={<Link className="panel-link" to="/customers">Directory <ArrowRight size={14} /></Link>}>
        <div className="compact-list">{customers.slice(0, 4).map((customer) => <div className="compact-row" key={customer.id}>
          <span className="avatar avatar-small">{customer.first_name?.[0]}{customer.last_name?.[0]}</span>
          <span className="compact-copy"><strong>{fullName(customer)}</strong><small>{customer.email}</small></span>
          <StatusBadge value={customer.kyc_status || "pending"} />
        </div>)}</div>
      </Panel>
      <Panel title="Pending loan applications" description="Applications that need attention" action={<Link className="panel-link" to="/loans">Review queue <ArrowRight size={14} /></Link>}>
        <div className="compact-list">{applications.filter((item) => ["submitted", "under_review"].includes(item.status)).slice(0, 4).map((item) => <div className="compact-row" key={item.id}>
          <span className="mini-icon amber"><BadgeDollarSign size={17} /></span>
          <span className="compact-copy"><strong>{item.id}</strong><small className="capitalize">{item.loan_type} loan · {formatMoney(item.requested_amount)}</small></span>
          <StatusBadge value={item.status} />
        </div>)}{applications.filter((item) => ["submitted", "under_review"].includes(item.status)).length === 0 && <div className="subtle-empty">No pending applications.</div>}</div>
      </Panel>
    </div>
  </div>;
}
