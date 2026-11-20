import { apiClient } from "../api/client.js";

export const customerService = {
  list: (params = {}) => apiClient.get("/customers", { params }),
  get: (id) => apiClient.get(`/customers/${id}`),
  create: (payload) => apiClient.post("/customers", payload),
  update: (id, payload) => apiClient.patch(`/customers/${id}`, payload),
  setStatus: (id, status) => apiClient.patch(`/customers/${id}/status`, { status }),
  deactivate: (id) => apiClient.delete(`/customers/${id}`),
  accountHistory: (id, params = {}) => apiClient.get(`/customers/${id}/account-history`, { params }),
  riskProfile: (id) => apiClient.get(`/customers/${id}/risk-profile`),
  uploadKyc: (id, documentType, file) => {
    const body = new FormData();
    body.set("document_type", documentType);
    body.set("file", file);
    return apiClient.post(`/customers/${id}/kyc-documents`, body);
  },
  reviewKyc: (customerId, documentId, status) =>
    apiClient.patch(`/customers/${customerId}/kyc-documents/${documentId}`, { status }),
};

export const accountService = {
  list: (params = {}) => apiClient.get("/accounts", { params }),
  types: () => apiClient.get("/accounts/types"),
  get: (id) => apiClient.get(`/accounts/${id}`),
  balance: (id) => apiClient.get(`/accounts/${id}/balance`),
  statement: (id, params = {}) => apiClient.get(`/accounts/${id}/statement`, { params }),
  create: (payload) => apiClient.post("/accounts", payload),
  freeze: (id) => apiClient.post(`/accounts/${id}/freeze`),
  unfreeze: (id) => apiClient.post(`/accounts/${id}/unfreeze`),
  approve: (id) => apiClient.post(`/accounts/${id}/approve`),
  activate: (id) => apiClient.post(`/accounts/${id}/activate`),
  close: (id) => apiClient.delete(`/accounts/${id}`),
};

export const transactionService = {
  list: (accountId, params = {}) => apiClient.get("/transactions", { params: { account_id: accountId, ...params } }),
  get: (id) => apiClient.get(`/transactions/${id}`),
  receipt: (id) => apiClient.get(`/transactions/${id}/receipt`),
  create: (payload, idempotencyKey) =>
    apiClient.post("/transactions", payload, { headers: { "Idempotency-Key": idempotencyKey } }),
  settle: (id) => apiClient.post(`/transactions/${id}/settle`),
  reject: (id) => apiClient.post(`/transactions/${id}/reject`),
  reverse: (id) => apiClient.post(`/transactions/${id}/reverse`),
  dailySummary: (accountId, date) =>
    apiClient.get(`/transactions/accounts/${accountId}/daily-summary`, { params: { date } }),
};

export const loanService = {
  eligibility: (payload) => apiClient.post("/loans/eligibility", payload),
  apply: (payload) => apiClient.post("/loans/applications", payload),
  applications: (params = {}) => apiClient.get("/loans/applications", { params }),
  application: (id) => apiClient.get(`/loans/applications/${id}`),
  review: (id) => apiClient.post(`/loans/applications/${id}/review`),
  approve: (id) => apiClient.post(`/loans/applications/${id}/approve`),
  reject: (id, reason) => apiClient.post(`/loans/applications/${id}/reject`, { reason }),
  loan: (id) => apiClient.get(`/loans/${id}`),
};

export const riskService = {
  fraudAlerts: (params = {}) => apiClient.get("/fraud/alerts", { params }),
  reviewFraud: (id, payload) => apiClient.post(`/fraud/alerts/${id}/review`, payload),
  creditScore: (payload) => apiClient.post("/credit-scoring/score", payload),
  amlCases: (params = {}) => apiClient.get("/aml/cases", { params }),
  amlCase: (id) => apiClient.get(`/aml/cases/${id}`),
  updateAmlCase: (id, payload) => apiClient.patch(`/aml/cases/${id}`, payload),
  amlRules: () => apiClient.get("/aml/rules"),
  updateAmlRule: (code, payload) => apiClient.put(`/aml/rules/${code}`, payload),
  amlSummary: () => apiClient.get("/aml/reports/summary"),
};

export const assistantService = {
  ask: (message) => apiClient.post("/banking-assistant/chat", { message }),
  history: () => apiClient.get("/banking-assistant/history"),
};
