import { useState } from "react";
import { Landmark, LockKeyhole, LogIn } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext.jsx";
import { apiErrorMessage } from "../api/client.js";

export default function Login() {
  const { isDemo, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try { await login(email, password, mfaCode || undefined); navigate("/", { replace: true }); }
    catch (requestError) { setError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return <div className="login-page">
    <div className="login-brand"><span className="brand-mark"><Landmark size={22} /></span><strong>IntelliBank <i>AI</i></strong></div>
    <form className="login-card" onSubmit={submit}>
      <div className="login-icon"><LockKeyhole size={21} /></div><h1>Welcome back</h1><p>Sign in to your IntelliBank operations workspace.</p>
      <label className="field"><span>Email address</span><input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label className="field"><span>Password</span><input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <label className="field"><span>Authenticator code <i>if enabled</i></span><input inputMode="numeric" maxLength={6} value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></label>
      {error && <div className="form-error">{error}</div>}
      <button disabled={busy} className="button button-primary login-submit"><LogIn size={17} /> {busy ? "Signing in…" : "Sign in securely"}</button>
      <Link to="/" className="login-demo-link">Return to illustrative demo</Link>
      <div className="login-note">Credentials are sent directly to your configured FastAPI backend. No credentials are stored in frontend source code.</div>
    </form>
    <span className="login-footer">Protected enterprise banking operations</span>
  </div>;
}
