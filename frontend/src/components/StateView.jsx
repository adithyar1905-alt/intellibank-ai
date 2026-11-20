import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";

export default function StateView({ loading, error, empty, emptyText = "No records found.", onRetry }) {
  if (loading) {
    return <div className="state-view"><LoaderCircle className="spin" size={22} /> Loading data…</div>;
  }
  if (error) {
    return (
      <div className="state-view state-error">
        <AlertCircle size={20} /><span>{error}</span>
        {onRetry && <button className="button button-quiet" onClick={onRetry}>Retry</button>}
      </div>
    );
  }
  if (empty) return <div className="state-view"><Inbox size={20} />{emptyText}</div>;
  return null;
}
