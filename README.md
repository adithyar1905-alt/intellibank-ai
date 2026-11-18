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

Database migrations provision the standard roles: Super Admin, Bank Admin,
Branch Manager, Bank Employee, Loan Officer, Risk Analyst, and Customer.
Registration assigns only the Customer role. Elevated roles must be assigned by
a trusted operator; never expose role assignment through public registration.
Use `Depends(require_roles(...))` or `Depends(require_permissions(...))` from
`app.core.authorization` to protect future bank-operation endpoints.
