import { Activity, BadgeDollarSign, CircleAlert, Users, Wallet } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import { DepositChart, GrowthChart, RiskChart, VolumeChart } from "../components/Charts.jsx";
import { monthlyData } from "../data/demo.js";

export default function Analytics() {
  return <div className="page-stack">
    <PageHeader eyebrow="BUSINESS INTELLIGENCE" title="Analytics" description="Explore financial performance and operational trends." action={<label className="date-filter">Reporting period <select defaultValue="6"><option value="3">Last 3 months</option><option value="6">Last 6 months</option><option value="12">Last 12 months</option></select></label>} />
    <div className="demo-notice"><CircleAlert size={16} /> Analytics are illustrative. No analytics aggregation API is currently mounted in the backend.</div>
    <div className="metric-grid four">
      <MetricCard title="Transaction volume" value="$29.7M" note="February · demo" change="+14.2%" icon={Activity} tone="blue" />
      <MetricCard title="Deposit balance" value="$19.5M" note="February · demo" change="+9.6%" icon={Wallet} tone="teal" />
      <MetricCard title="Customer growth" value="642" note="new customers this month" change="+7.7%" icon={Users} tone="purple" />
      <MetricCard title="Loan portfolio" value="$8.2M" note="illustrative balance" change="+4.1%" icon={BadgeDollarSign} tone="amber" />
    </div>
    <div className="grid-two">
      <Panel title="Financial performance" description="Transaction value · USD millions"><VolumeChart data={monthlyData} /></Panel>
      <Panel title="Deposit analytics" description="Deposits compared with withdrawals"><DepositChart data={monthlyData} /></Panel>
      <Panel title="Customer growth" description="Cumulative customer registrations"><GrowthChart data={monthlyData} /></Panel>
      <Panel title="Fraud analytics" description="Illustrative risk classification"><RiskChart /></Panel>
    </div>
    <Panel title="Analytics scope" description="Live data integration status">
      <div className="integration-list"><div><span className="integration-indicator unavailable" /> Backend analytics API <StatusText text="Not mounted" /></div><div><span className="integration-indicator demo" /> Charts and KPIs <StatusText text="Illustrative demo data" /></div></div>
    </Panel>
  </div>;
}

function StatusText({ text }) { return <span className="integration-status">{text}</span>; }
