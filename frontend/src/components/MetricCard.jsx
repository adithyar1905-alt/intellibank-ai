import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export default function MetricCard({ title, value, note, change, icon: Icon, tone = "blue" }) {
  const positive = !String(change || "").startsWith("-");
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{title}</span>
        {Icon && <span className={`metric-icon ${tone}`}><Icon size={19} /></span>}
      </div>
      <strong className="metric-value">{value}</strong>
      <div className="metric-foot">
        {change && <span className={`metric-change ${positive ? "up" : "down"}`}>
          {positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}{change}
        </span>}
        <span>{note}</span>
      </div>
    </article>
  );
}
