import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import StateView from "./StateView.jsx";

export default function DataTable({
  columns,
  rows = [],
  loading = false,
  error = "",
  onRetry,
  searchPlaceholder = "Search records…",
  pageSize = 6,
  emptyText = "No matching records.",
  rowKey = "id",
  onRowClick,
  toolbar,
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => columns.some((column) =>
      String(column.searchValue ? column.searchValue(row) : row[column.key] ?? "").toLowerCase().includes(needle),
    ));
  }, [columns, query, rows]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pages - 1);
  const visible = filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  return (
    <div className="table-wrap">
      <div className="table-toolbar">
        <label className="search-field">
          <Search size={16} />
          <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder={searchPlaceholder} />
        </label>
        {toolbar && <div className="table-toolbar-actions">{toolbar}</div>}
      </div>
      <StateView loading={loading} error={error} empty={!loading && !error && rows.length === 0} emptyText={emptyText} onRetry={onRetry} />
      {!loading && !error && rows.length > 0 && filtered.length === 0 && <div className="table-empty">No records match “{query}”.</div>}
      {!loading && !error && visible.length > 0 && (
        <>
          <div className="table-scroll">
            <table>
              <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
              <tbody>
                {visible.map((row, index) => (
                  <tr key={row[rowKey] || index} className={onRowClick ? "clickable-row" : ""} onClick={() => onRowClick?.(row)}>
                    {columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : row[column.key] ?? "—"}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="table-pagination">
            <span>Showing {currentPage * pageSize + 1}–{Math.min((currentPage + 1) * pageSize, filtered.length)} of {filtered.length}</span>
            <div>
              <button aria-label="Previous page" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={17} /></button>
              <span>{currentPage + 1} / {pages}</span>
              <button aria-label="Next page" disabled={currentPage >= pages - 1} onClick={() => setPage(currentPage + 1)}><ChevronRight size={17} /></button>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
