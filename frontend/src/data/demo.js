export const demoCustomers = [
  { id: "CUS-20481", customer_number: "CUS-20481", first_name: "Ava", last_name: "Mitchell", email: "ava.mitchell@example.com", phone_number: "+1 415 555 0184", status: "active", kyc_status: "verified", created_at: "2025-02-14T10:12:00Z", user_id: "USR-1001", kyc_documents: [] },
  { id: "CUS-20480", customer_number: "CUS-20480", first_name: "Noah", last_name: "Patel", email: "noah.patel@example.com", phone_number: "+1 212 555 0139", status: "active", kyc_status: "pending", created_at: "2025-02-13T08:40:00Z", user_id: "USR-1002", kyc_documents: [] },
  { id: "CUS-20479", customer_number: "CUS-20479", first_name: "Sophia", last_name: "Chen", email: "sophia.chen@example.com", phone_number: "+1 646 555 0122", status: "active", kyc_status: "verified", created_at: "2025-02-12T14:28:00Z", user_id: "USR-1003", kyc_documents: [] },
  { id: "CUS-20478", customer_number: "CUS-20478", first_name: "Liam", last_name: "Johnson", email: "liam.johnson@example.com", phone_number: "+1 312 555 0107", status: "inactive", kyc_status: "rejected", created_at: "2025-02-11T11:05:00Z", user_id: "USR-1004", kyc_documents: [] },
  { id: "CUS-20477", customer_number: "CUS-20477", first_name: "Isabella", last_name: "Garcia", email: "isabella.garcia@example.com", phone_number: "+1 305 555 0171", status: "active", kyc_status: "verified", created_at: "2025-02-10T09:18:00Z", user_id: "USR-1005", kyc_documents: [] },
  { id: "CUS-20476", customer_number: "CUS-20476", first_name: "Ethan", last_name: "Kim", email: "ethan.kim@example.com", phone_number: "+1 206 555 0113", status: "blocked", kyc_status: "pending", created_at: "2025-02-08T16:42:00Z", user_id: "USR-1006", kyc_documents: [] },
  { id: "CUS-20475", customer_number: "CUS-20475", first_name: "Mia", last_name: "Brown", email: "mia.brown@example.com", phone_number: "+1 617 555 0146", status: "active", kyc_status: "verified", created_at: "2025-02-07T12:15:00Z", user_id: "USR-1007", kyc_documents: [] },
];

export const demoAccounts = [
  { id: "ACC-83921", customer_id: "CUS-20481", account_type: "savings", account_number_last4: "4821", currency: "USD", current_balance: 28450.72, available_balance: 28450.72, status: "active", created_at: "2024-06-11T12:00:00Z" },
  { id: "ACC-83920", customer_id: "CUS-20480", account_type: "current", account_number_last4: "6390", currency: "USD", current_balance: 142250, available_balance: 142250, status: "active", created_at: "2024-06-10T12:00:00Z" },
  { id: "ACC-83919", customer_id: "CUS-20479", account_type: "savings", account_number_last4: "1774", currency: "USD", current_balance: 7600, available_balance: 7600, status: "frozen", created_at: "2024-06-08T12:00:00Z" },
  { id: "ACC-83918", customer_id: "CUS-20478", account_type: "fixed_deposit", account_number_last4: "9013", currency: "USD", current_balance: 55000, available_balance: 55000, status: "pending_approval", created_at: "2024-06-07T12:00:00Z" },
  { id: "ACC-83917", customer_id: "CUS-20477", account_type: "savings", account_number_last4: "3206", currency: "USD", current_balance: 31890.4, available_balance: 31890.4, status: "active", created_at: "2024-06-05T12:00:00Z" },
];

export const demoTransactions = [
  { id: "TXN-591842", reference: "IB-20250218-591842", account_id: "ACC-83921", transaction_type: "upi", amount: 1250, currency: "USD", status: "completed", description: "Merchant payment", created_at: "2025-02-18T14:31:00Z" },
  { id: "TXN-591841", reference: "IB-20250218-591841", account_id: "ACC-83920", transaction_type: "transfer", amount: 8400, currency: "USD", status: "review_required", description: "International supplier", created_at: "2025-02-18T14:22:00Z" },
  { id: "TXN-591840", reference: "IB-20250218-591840", account_id: "ACC-83917", transaction_type: "deposit", amount: 5400, currency: "USD", status: "completed", description: "Payroll deposit", created_at: "2025-02-18T13:58:00Z" },
  { id: "TXN-591839", reference: "IB-20250218-591839", account_id: "ACC-83919", transaction_type: "withdrawal", amount: 780, currency: "USD", status: "failed", description: "ATM withdrawal", created_at: "2025-02-18T13:42:00Z" },
  { id: "TXN-591838", reference: "IB-20250218-591838", account_id: "ACC-83920", transaction_type: "neft", amount: 2300, currency: "USD", status: "completed", description: "Vendor settlement", created_at: "2025-02-18T12:16:00Z" },
  { id: "TXN-591837", reference: "IB-20250218-591837", account_id: "ACC-83921", transaction_type: "imps", amount: 460, currency: "USD", status: "completed", description: "Instant transfer", created_at: "2025-02-18T11:40:00Z" },
];

export const demoApplications = [
  { id: "APP-9001", customer_id: "CUS-20481", loan_type: "home", requested_amount: 420000, requested_term_months: 240, declared_monthly_income: 14500, status: "under_review", submitted_at: "2025-02-18T10:00:00Z", documents: [] },
  { id: "APP-9002", customer_id: "CUS-20480", loan_type: "business", requested_amount: 125000, requested_term_months: 84, declared_monthly_income: 24000, status: "submitted", submitted_at: "2025-02-17T15:22:00Z", documents: [] },
  { id: "APP-9003", customer_id: "CUS-20479", loan_type: "education", requested_amount: 48000, requested_term_months: 60, declared_monthly_income: 7800, status: "approved", submitted_at: "2025-02-16T09:48:00Z", documents: [] },
  { id: "APP-9004", customer_id: "CUS-20477", loan_type: "personal", requested_amount: 18000, requested_term_months: 36, declared_monthly_income: 9200, status: "rejected", submitted_at: "2025-02-15T13:11:00Z", documents: [] },
];

export const demoFraudAlerts = [
  { id: "ALT-7201", customer_id: "CUS-20480", transaction_id: "TXN-591841", score: 0.94, severity: "critical", status: "open", description: "Unusual transfer amount and velocity", created_at: "2025-02-18T14:22:00Z", details: { illustrative: true } },
  { id: "ALT-7200", customer_id: "CUS-20479", transaction_id: "TXN-591839", score: 0.68, severity: "medium", status: "investigating", description: "Multiple failed access attempts", created_at: "2025-02-18T12:42:00Z", details: { illustrative: true } },
  { id: "ALT-7199", customer_id: "CUS-20476", transaction_id: "TXN-591810", score: 0.32, severity: "low", status: "open", description: "New device and unusual time", created_at: "2025-02-18T09:12:00Z", details: { illustrative: true } },
];

export const demoAmlCases = [
  { id: "AML-1402", case_number: "AML-2025-01402", customer_id: "CUS-20480", transaction_id: "TXN-591841", rule_code: "large_transfer", severity: "high", status: "open", findings: {}, created_at: "2025-02-18T14:22:00Z" },
  { id: "AML-1401", case_number: "AML-2025-01401", customer_id: "CUS-20476", transaction_id: "TXN-591810", rule_code: "rapid_activity", severity: "medium", status: "investigating", findings: {}, created_at: "2025-02-18T09:12:00Z" },
];

export const monthlyData = [
  { month: "Sep", transactions: 18.4, deposits: 12.2, withdrawals: 8.6, customers: 420 },
  { month: "Oct", transactions: 20.1, deposits: 13.8, withdrawals: 9.2, customers: 468 },
  { month: "Nov", transactions: 23.8, deposits: 15.1, withdrawals: 10.1, customers: 502 },
  { month: "Dec", transactions: 25.4, deposits: 16.4, withdrawals: 11.6, customers: 548 },
  { month: "Jan", transactions: 24.9, deposits: 17.8, withdrawals: 12.4, customers: 596 },
  { month: "Feb", transactions: 29.7, deposits: 19.5, withdrawals: 13.2, customers: 642 },
];

export const formatMoney = (value, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value || 0));
export const fullName = (customer) => `${customer?.first_name || ""} ${customer?.last_name || ""}`.trim() || "Customer";
