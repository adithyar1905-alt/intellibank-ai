import { useMemo, useState } from "react";
import { Download, FileSpreadsheet, FileText, Info } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import Panel from "../components/Panel.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { demoTransactions, demoCustomers, demoApplications, formatMoney } from "../data/demo.js";

const reportDefinitions = [
  { title: "Daily operations", category: "Operations", date: "Feb 18, 2025", status: "Ready", description: "Daily transaction and operational overview" },
  { title: "Monthly customer growth", category: "Customers", date: "Feb 01, 2025", status: "Ready", description: "Registrations and KYC progress" },
  { title: "Loan pipeline", category: "Lending", date: "Feb 18, 2025", status: "Ready", description: "Applications by status and loan type" },
  { title: "Fraud monitoring", category: "Risk", date: "Feb 18, 2025", status: "Illustrative", description: "Example alert and risk distribution" },
];

function downloadCsv(filename, rows) {
  const csv = rows.map((row) => row.map((item) => `"${String(item ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  const [range, setRange] = useState("month");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const columns = useMemo(() => [
    { key: "title", label: "Report", render: (row) => <div className="table-person"><span className="mini-icon blue"><FileText size={17} /></span><span><strong>{row.title}</strong><small>{row.description}</small></span></div> },
    { key: "category", label: "Category" },
    { key: "date", label: "Period ending" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Export", render: () => <div className="row-actions"><button className="icon-button" aria-label="Export Excel" title="Export demo Excel workbook" onClick={exportExcel} disabled={exporting}><FileSpreadsheet size={16} /></button><button className="icon-button" aria-label="Print report" title="Print or save to PDF" onClick={() => window.print()}><Download size={16} /></button></div> },
  ], [exporting]);
  function exportAll() {
    downloadCsv("intellibank-report-demo.csv", [
      ["Report", "Category", "Count", "Data mode"],
      ["Transactions", "Operations", demoTransactions.length, "Illustrative demo"],
      ["Customers", "Customers", demoCustomers.length, "Illustrative demo"],
      ["Loan applications", "Lending", demoApplications.length, "Illustrative demo"],
    ]);
  }
  async function exportExcel() {
    setExportError("");
    setExporting(true);
    try {
      const { default: ExcelJS } = await import("exceljs");
      const workbook = new ExcelJS.Workbook();
      workbook.creator = "IntelliBank AI";
      workbook.subject = "Illustrative demo reports";

      const addSheet = (name, headers, rows) => {
        const sheet = workbook.addWorksheet(name);
        sheet.addRow(headers);
        rows.forEach((row) => sheet.addRow(row));
        sheet.views = [{ state: "frozen", ySplit: 1 }];
        sheet.autoFilter = {
          from: { row: 1, column: 1 },
          to: { row: 1, column: headers.length },
        };
        sheet.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
        sheet.getRow(1).fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: "FF17324D" },
        };
        headers.forEach((header, index) => {
          sheet.getColumn(index + 1).width = Math.min(Math.max(String(header).length + 4, 14), 30);
        });
        return sheet;
      };

      addSheet("Summary", ["Report", "Category", "Records", "Data mode"], [
        ["Transactions", "Operations", demoTransactions.length, "Illustrative demo"],
        ["Customers", "Customers", demoCustomers.length, "Illustrative demo"],
        ["Loan applications", "Lending", demoApplications.length, "Illustrative demo"],
      ]);
      addSheet("Customers", ["Customer ID", "First name", "Last name", "Email", "Phone", "Status", "KYC status", "Registered"], demoCustomers.map((customer) => [
        customer.id, customer.first_name, customer.last_name, customer.email, customer.phone_number,
        customer.status, customer.kyc_status, customer.created_at,
      ]));
      const transactionsSheet = addSheet("Transactions", ["Transaction ID", "Reference", "Account ID", "Type", "Amount", "Currency", "Status", "Description", "Created"], demoTransactions.map((transaction) => [
        transaction.id, transaction.reference, transaction.account_id, transaction.transaction_type,
        transaction.amount, transaction.currency, transaction.status, transaction.description, transaction.created_at,
      ]));
      transactionsSheet.getColumn(5).numFmt = "#,##0.00";
      const loansSheet = addSheet("Loan applications", ["Application ID", "Customer ID", "Loan type", "Requested amount", "Term (months)", "Declared monthly income", "Status", "Submitted"], demoApplications.map((application) => [
        application.id, application.customer_id, application.loan_type, application.requested_amount,
        application.requested_term_months, application.declared_monthly_income, application.status, application.submitted_at,
      ]));
      loansSheet.getColumn(4).numFmt = "#,##0.00";
      loansSheet.getColumn(6).numFmt = "#,##0.00";

      const buffer = await workbook.xlsx.writeBuffer();
      const blob = new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "intellibank-report-demo.xlsx";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      console.error("Could not export the Excel report.", error);
      setExportError("Excel export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  }
  return <div className="page-stack">
    <PageHeader eyebrow="REPORTING" title="Reports" description="Review daily, monthly, customer, transaction, loan, and risk reports." action={<label className="date-filter">Date range <select value={range} onChange={(event) => setRange(event.target.value)}><option value="day">Today</option><option value="month">This month</option><option value="quarter">This quarter</option></select></label>} />
    <div className="demo-notice"><Info size={16} /> Report generation APIs are not mounted. Downloads use illustrative demo records; PDF export uses your browser’s print dialog.</div>
    <Panel title="Available reports" description={`Showing ${range === "day" ? "daily" : range === "quarter" ? "quarterly" : "monthly"} report templates`} action={<div className="row-actions"><button className="button button-outline" onClick={exportAll}><FileSpreadsheet size={16} /> Export demo CSV</button><button className="button button-outline" onClick={exportExcel} disabled={exporting}><FileSpreadsheet size={16} /> {exporting ? "Preparing Excel…" : "Export Excel"}</button></div>}>
      {exportError && <p className="form-error" role="alert">{exportError}</p>}
      <DataTable columns={columns} rows={reportDefinitions} pageSize={6} searchPlaceholder="Search report templates…" />
    </Panel>
    <Panel title="Data included in sample export" description="The export contains demo counts only">
      <div className="report-sample"><span>Customer records<strong>{demoCustomers.length}</strong></span><span>Transaction records<strong>{demoTransactions.length}</strong></span><span>Loan applications<strong>{demoApplications.length}</strong></span><span>Sample transaction volume<strong>{formatMoney(demoTransactions.reduce((sum, item) => sum + item.amount, 0))}</strong></span></div>
    </Panel>
  </div>;
}
