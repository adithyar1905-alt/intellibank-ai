# intellibank-ai
An enterprise-grade AI-powered banking management platform built with Python FastAPI, React, PostgreSQL, and Machine Learning. Includes account management, secure transactions, loan processing, fraud detection, credit scoring, AML monitoring, AI banking assistant, and financial analytics.

## Backend database setup

The backend uses PostgreSQL, SQLAlchemy 2, and Alembic. From the repository root,
install the backend dependencies, copy `backend/.env.example` to `backend/.env`,
and set `DATABASE_URL` to the PostgreSQL connection URL for your environment:

```powershell
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
Set-Location backend
alembic upgrade head
```

Keep `backend/.env` private; it is excluded from Git. To verify database access
and ORM constraints using the local SQLite test database:

```powershell
python -m unittest discover -s tests -v
```

Create future schema changes as Alembic revisions from the `backend` directory:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

### Accounts, transactions, and loans

The account, transaction, immutable ledger, and loan APIs are mounted under
`/api/v1/accounts`, `/api/v1/transactions`, and `/api/v1/loans`. Before using
them against PostgreSQL, apply the account/transaction/loan workflow migration:

```powershell
Set-Location backend
alembic upgrade head
```

The migration provisions Savings Account, Current Account, Fixed Deposit, and
Recurring Deposit account types. New accounts require bank approval followed
by activation. Transaction requests require an `Idempotency-Key` header;
internal transfers post debit/credit ledger entries atomically. NEFT, RTGS,
IMPS, and UPI requests remain pending until an authorized settlement/rejection
action is made; payment-network integrations are not configured by this API.
Transactions flagged by the fraud policy stay in `review_required` without
ledger posting until an authorized reviewer approves them.
Loan applications require verified customer KYC and an active owned
disbursement account. Loan documents share the encrypted private KYC storage
configuration. Use `/api/v1/loans/eligibility`, then submit an application,
upload supporting documents, and have a Loan Officer review and approve it.

### Authentication

The API exposes Swagger UI at `/docs` and authentication routes under
`/api/v1/auth`. Configure `JWT_SECRET_KEY` with at least 32 random bytes and
`MFA_ENCRYPTION_KEY` with a Fernet key before deployment. Generate the latter
with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and the JWT key with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Configure SMTP settings in `backend/.env` to enable password reset email delivery.

Use `/api/v1/auth/register` to create customer accounts. Login accepts the
OAuth2 password form (`username` is the email address), and Swagger's **Authorize**
dialog uses the same flow. Refresh tokens rotate on use. A reset email is sent
only when SMTP is configured; reset tokens are one-time and stored hashed.
Authenticator-based MFA uses TOTP and stores its secret encrypted at rest. Keep
the MFA encryption key stable and backed up; changing it prevents existing
authenticator secrets from being decrypted.

### Customer management

Customer-management endpoints are available under `/api/v1/customers`. Bank
employees, branch managers, and bank admins can create and maintain customer
profiles; customer accounts can view their own profile, KYC documents, and
account history. Customer deletion is a soft deactivation so linked banking and
audit history is retained. The API also supports customer search, status
management, KYC document review, and risk profiles for risk analysts and bank
staff.

Generate a separate Fernet key for KYC files with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and set `KYC_ENCRYPTION_KEY` before enabling document uploads. Set
`KYC_STORAGE_PATH` to a private, non-public
directory with restricted filesystem access. KYC documents are validated,
encrypted at rest, and never served from a static path. Install the backend
requirements and run the customer API tests from `backend` with:

```powershell
pytest tests/api/test_customers.py -q
```

Database migrations provision the standard roles: Super Admin, Bank Admin,
Branch Manager, Bank Employee, Loan Officer, Risk Analyst, and Customer.
Registration assigns only the Customer role. Elevated roles must be assigned by
a trusted operator; never expose role assignment through public registration.
Use `Depends(require_roles(...))` or `Depends(require_permissions(...))` from
`app.core.authorization` to protect future bank-operation endpoints.

### Fraud detection, credit scoring, AML, and banking assistant

The AI-assisted modules are mounted under `/api/v1` and are documented in
Swagger at `/docs`. Apply the newest PostgreSQL migration before using the AML
case and assistant conversation-history tables:

```powershell
Set-Location backend
alembic upgrade head
```

Fraud evaluation runs inside successful transaction creation and uses the
configured policy thresholds (`FRAUD_LARGE_AMOUNT_THRESHOLD`,
`FRAUD_HOURLY_COUNT_THRESHOLD`, and the `FRAUD_*_THRESHOLD` risk cutoffs).
`FRAUD_MODEL_PATH` selects the optional trained model artifact. When a
transaction reaches the review threshold it is persisted in
`review_required` status without posting ledger entries; a role-authorized
human must approve or reject it through the fraud review workflow. A risk
score never freezes an account. Location change is currently a source-IP
change signal, not a geographic location verification service.

Fraud routes:

- `GET /api/v1/fraud/alerts` — risk-team alert queue.
- `POST /api/v1/fraud/alerts/{alert_id}/review` — human decision and transaction release/rejection.
- `POST /api/v1/fraud/model/train` — train and evaluate using supplied, labeled historical rows.

The fraud training dataset must contain the documented numeric features and
the `is_fraud` label, with both classes represented. Only authorized, real,
correctly labeled transactions should be used. Training returns held-out
metrics and writes the artifact under the private model directory by default;
no trained model is shipped with the application.

AML monitoring evaluates accepted transactions against configurable,
database-backed rules and creates immutable findings for investigator review.
The default rules include large transactions, rapid activity, repeated
unresolved fraud alerts, and high-value external payment rails. Rules are
configurable by compliance roles; they never freeze accounts or determine
criminal activity. Investigation status changes, assignments, rule updates,
and report access are role protected; case creation, status changes, and rule
updates are audited.

AML routes:

- `GET /api/v1/aml/cases` and `GET /api/v1/aml/cases/{case_id}` — investigation queue/details.
- `PATCH /api/v1/aml/cases/{case_id}` — assign or transition a case through human investigation.
- `POST /api/v1/aml/evaluate/{transaction_id}` — authorized manual re-evaluation.
- `GET /api/v1/aml/rules` and `PUT /api/v1/aml/rules/{code}` — view/configure detection policy.
- `GET /api/v1/aml/reports/summary` — aggregate case counts by status and severity.

Credit scores are indicative risk assessments, not automated loan decisions.
The scorer currently uses applicant-declared income, debt, and requested-loan
values only; it does not load credit-bureau, repayment, demographic, or
transaction histories. Its optional scikit-learn training pipeline accepts
only validated, real, authorized labeled outcomes and does not fabricate
customer histories. Call `train_model()` from
`app.ai_services.credit_scoring.training` with that dataset and an artifact
path; configure the resulting artifact with `CREDIT_MODEL_PATH`. If no model
is configured, scoring uses a clearly identified affordability baseline. If a
configured artifact cannot be loaded, the API reports an error instead of
silently switching to the baseline. Predictions include input explanations
and limitations and must be reviewed by a qualified loan officer. Submit a
scoring request to `POST /api/v1/credit-scoring/score`; see Swagger for the
validated request fields and response.

The banking assistant uses an adapter boundary for approved LLM providers and
controlled read-only banking data access. It verifies customer ownership,
persists conversation history by authenticated user/customer, rate-limits
requests in-process, and explicitly refuses to perform transfers, deposits,
withdrawals, or other transactions. The in-process limiter must be replaced
with shared storage before deploying multiple API workers. Configure
`AI_ASSISTANT_PROVIDER`, `AI_ASSISTANT_API_URL`, `AI_ASSISTANT_API_KEY`,
`AI_ASSISTANT_MODEL`, and `AI_ASSISTANT_TIMEOUT_SECONDS` only after reviewing
the provider's data-handling and retention terms. Set
`AI_ASSISTANT_PROVIDER=openai_compatible` to enable the OpenAI-compatible
adapter; it is disabled by default. Only generic FAQ/financial-education
questions are sent to the provider. Customer financial data is not sent to
the LLM adapter; user-specific balance, history, and loan answers are
generated from ownership-checked services.

Assistant routes:

- `POST /api/v1/banking-assistant/chat` — authenticated, verified customer question.
- `GET /api/v1/banking-assistant/history` — that user's persisted conversation history.

The assistant supports account balance, recent transaction history, owned loan
information, and general education/FAQ responses. Financial actions receive an
explicit refusal and are never passed to transaction services. Account numbers
are masked, and transaction history returned by the assistant is capped.

Run the focused AI module tests and then the full backend suite from `backend`:

```powershell
pytest tests/api/test_ai_monitoring.py tests/api/test_credit_scoring.py tests/api/test_banking_assistant.py -q
pytest -q
```
