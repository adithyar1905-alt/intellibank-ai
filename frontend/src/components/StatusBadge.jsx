export default function StatusBadge({ value }) {
  const text = String(value || "unknown").replaceAll("_", " ");
  const tone = /active|completed|verified|approved|paid|closed|low/i.test(text)
    ? "success"
    : /pending|review|required|investigating|medium|submitted|under review/i.test(text)
      ? "warning"
      : /failed|rejected|blocked|frozen|critical|high|overdue/i.test(text)
        ? "danger"
        : "neutral";
  return <span className={`status-badge ${tone}`}><span className="status-dot" />{text}</span>;
}
