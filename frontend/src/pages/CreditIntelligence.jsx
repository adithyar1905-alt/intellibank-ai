import { useState } from "react";
import { BrainCircuit, CircleAlert, Fingerprint, Info, Sparkles } from "lucide-react";
import { riskService } from "../services/banking.js";
import { demoCustomers, formatMoney, fullName } from "../data/demo.js";
import { useAuth } from "../app/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import MetricCard from "../components/MetricCard.jsx";
import Panel from "../components/Panel.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const illustrativeProfiles = [
  { customer: demoCustomers[2], score: 742, risk: "moderate", amount: 125000, probability: "82%" },
  { customer: demoCustomers[4], score: 681, risk: "moderate", amount: 76000, probability: "76%" },
  { customer: demoCustomers[0], score: 805, risk: "low", amount: 215000, probability: "91%" },
];

export default function CreditIntelligence() {
  const { isDemo } = useAuth();
  const [form, setForm] = useState({ customer_id: "", monthly_income: "", monthly_debt: "", requested_amount: "", requested_term_months: "36" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function scoreCustomer(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isDemo) {
        const ratio = (Number(form.monthly_debt) + Number(form.requested_amount) / Number(form.requested_term_months)) / Number(form.monthly_income);
        const score = Math.max(0, Math.min(1000, Math.round(1000 * (1 - ratio))));
        setResult({ customer_id: form.customer_id, score, band: score > 700 ? "high" : score > 500 ? "moderate" : "low", probability_of_repayment: score / 1000, indicative_only: true, human_review_required: true, model_version: "demo-affordability", limitations: ["Illustrative frontend calculation only; not a credit decision.", "Only the values supplied in this form are used."], explanations: [] });
      } else {
        const { data } = await riskService.creditScore({
          customer_id: form.customer_id,
          monthly_income: Number(form.monthly_income),
          monthly_debt: Number(form.monthly_debt),
          requested_amount: Number(form.requested_amount),
          requested_term_months: Number(form.requested_term_months),
        });
        setResult(data);
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Credit assessment failed.");
    } finally { setLoading(false); }
  }

  return <div className="page-stack">
    <PageHeader eyebrow="CREDIT RISK" title="Credit intelligence" description="Review applicant affordability signals and illustrative credit-risk insights." />
    {isDemo && <div className="demo-notice"><CircleAlert size={16} /> All demo scores are illustrative. No credit bureau or real repayment history is used.</div>}
    <div className="metric-grid three">
      <MetricCard title="Profiles displayed" value={illustrativeProfiles.length} note="illustrative portfolio examples" icon={Fingerprint} tone="blue" />
      <MetricCard title="Human review" value="Required" note="for every credit decision" icon={BrainCircuit} tone="amber" />
      <MetricCard title="Data provenance" value="Declared" note="income and debt inputs only" icon={Info} tone="teal" />
    </div>
    <div className="grid-two">
      <Panel title="Customer credit profiles" description="Sample scoring profiles · illustrative only">
        <div className="credit-profile-list">{illustrativeProfiles.map((item) => <article className="credit-profile" key={item.customer.id}>
          <div className="table-person"><span className="avatar avatar-small">{item.customer.first_name[0]}{item.customer.last_name[0]}</span><span><strong>{fullName(item.customer)}</strong><small>{item.customer.customer_number}</small></span></div>
          <div className="score-pill"><strong>{item.score}</strong><small>Illustrative score</small></div>
          <StatusBadge value={item.risk} />
          <div className="credit-profile-foot"><span>Eligibility estimate <strong>{formatMoney(item.amount)}</strong></span><span>Repayment signal <strong>{item.probability}</strong></span></div>
        </article>)}</div>
      </Panel>
      <Panel title="AI affordability assessment" description="Assess only the inputs provided; score is not a lending decision">
        <form className="form-grid" onSubmit={scoreCustomer}>
          <label className="field full"><span>Customer ID</span><input required value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })} placeholder="Customer UUID" /></label>
          <label className="field"><span>Monthly income</span><input required min="0.01" step="0.01" type="number" value={form.monthly_income} onChange={(event) => setForm({ ...form, monthly_income: event.target.value })} /></label>
          <label className="field"><span>Monthly debt</span><input required min="0" step="0.01" type="number" value={form.monthly_debt} onChange={(event) => setForm({ ...form, monthly_debt: event.target.value })} /></label>
          <label className="field"><span>Requested amount</span><input required min="0.01" step="0.01" type="number" value={form.requested_amount} onChange={(event) => setForm({ ...form, requested_amount: event.target.value })} /></label>
          <label className="field"><span>Term (months)</span><input required min="1" max="360" type="number" value={form.requested_term_months} onChange={(event) => setForm({ ...form, requested_term_months: event.target.value })} /></label>
          {error && <p className="form-error full">{error}</p>}
          <div className="form-actions full"><button disabled={loading} className="button button-primary"><Sparkles size={16} /> {loading ? "Assessing…" : "Generate assessment"}</button></div>
        </form>
        {result && <div className="score-result"><div className="score-result-main"><span>Indicative score</span><strong>{result.score}<small>/ 1000</small></strong><StatusBadge value={result.band} /></div><div className="score-result-copy"><p>Repayment probability estimate: <strong>{Math.round(result.probability_of_repayment * 100)}%</strong></p><p><strong>Human review required.</strong> This output is not an approval or credit decision.</p><ul>{result.limitations?.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div></div>}
      </Panel>
    </div>
    <div className="notice-card"><Info size={18} /><div><strong>Model limitations & responsible use</strong><p>Scores use declared affordability inputs and may not include repayment history, bureau data, or full policy requirements. A qualified loan officer must assess the application and verify evidence.</p></div></div>
  </div>;
}
