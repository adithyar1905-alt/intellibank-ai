import { useCallback, useState } from "react";
import { KeyRound, LockKeyhole, Shield, ShieldCheck, UserRound, Users } from "lucide-react";
import { useAuth } from "../app/AuthContext.jsx";
import { useApiResource } from "../app/useApiResource.js";
import { authService } from "../services/auth.js";
import { apiErrorMessage } from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import Panel from "../components/Panel.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const demoProfile = { id: "demo-admin", email: "admin@intellibank.ai", is_active: true, is_verified: true, roles: ["Super Admin"], permissions: ["*"] };

export default function Settings() {
  const { isDemo, user } = useAuth();
  const loadProfile = useCallback(() => authService.me(), []);
  const loadRoles = useCallback(() => authService.roles(), []);
  const { data: profile, loading, error, refresh } = useApiResource(loadProfile, demoProfile);
  const { data: roles, error: rolesError } = useApiResource(loadRoles, ["Super Admin", "Bank Admin", "Branch Manager", "Loan Officer", "Risk Analyst", "Customer"]);
  const [mfa, setMfa] = useState(null);
  const [mfaError, setMfaError] = useState("");
  const [code, setCode] = useState("");
  const [setupInfo, setSetupInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  async function checkMfa() {
    try { setMfa((await authService.mfaStatus()).data); setMfaError(""); }
    catch (requestError) { setMfaError(apiErrorMessage(requestError)); }
  }
  async function setup() {
    setBusy(true);
    try { setSetupInfo((await authService.setupMfa()).data); setMfaError(""); }
    catch (requestError) { setMfaError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }
  async function confirm(event) {
    event.preventDefault();
    setBusy(true);
    try { setMfa((await authService.confirmMfa(code)).data); setSetupInfo(null); setCode(""); setMfaError(""); }
    catch (requestError) { setMfaError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }

  return <div className="page-stack">
    <PageHeader eyebrow="ADMINISTRATION" title="Settings" description="Review your profile, assigned access, and security options." action={!isDemo && <button className="button button-outline" onClick={() => refresh()}>Refresh profile</button>} />
    {isDemo && <div className="demo-notice">You’re in demo mode. Security and identity settings require an authenticated backend session.</div>}
    <div className="grid-two">
      <Panel title="Admin profile" description="Authenticated identity details">
        {loading ? <div className="state-view">Loading profile…</div> : error ? <div className="inline-error">{error}</div> : <div className="settings-profile">
          <span className="avatar avatar-large"><UserRound size={22} /></span><div><h3>{profile?.email || user.email}</h3><span>{profile?.id}</span></div>
          <div className="detail-grid"><div><small>Account status</small><StatusBadge value={profile?.is_active ? "active" : "inactive"} /></div><div><small>Email verification</small><StatusBadge value={profile?.is_verified ? "verified" : "pending"} /></div><div><small>Role</small><strong>{profile?.roles?.join(", ") || "—"}</strong></div></div>
        </div>}
      </Panel>
      <Panel title="Security settings" description="Multi-factor authentication">
        {!isDemo && <button className="button button-outline" onClick={checkMfa}><LockKeyhole size={16} /> Check MFA status</button>}
        {mfa && <div className="mfa-state"><span><ShieldCheck size={18} /> Multi-factor authentication</span><StatusBadge value={mfa.enabled ? "enabled" : "disabled"} /></div>}
        {!isDemo && !mfa?.enabled && <button disabled={busy} className="button button-primary mfa-setup" onClick={setup}><KeyRound size={16} /> Start authenticator setup</button>}
        {setupInfo && <form className="mfa-setup-box" onSubmit={confirm}><p>Scan the QR provisioning URI in your authenticator app, then enter its six-digit code.</p><code>{setupInfo.provisioning_uri}</code><label className="field"><span>Authenticator code</span><input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} /></label><button disabled={busy} className="button button-primary">Confirm MFA</button></form>}
        {mfaError && <p className="form-error">{mfaError}</p>}
        <p className="form-hint">The MFA setup secret is sensitive. Do not share it. Role and security changes are performed only by authorized backend APIs.</p>
      </Panel>
    </div>
    <Panel title="Roles and permissions" description="Role catalog and this session’s effective access">
      {rolesError && <div className="inline-error">{rolesError}</div>}
      <div className="settings-roles"><div className="roles-current"><span className="mini-icon teal"><Shield size={17} /></span><div><strong>Current roles</strong><small>{profile?.roles?.join(", ") || "No roles returned"}</small></div></div><div className="roles-current"><span className="mini-icon blue"><Users size={17} /></span><div><strong>Available roles</strong><small>{Array.isArray(roles) ? roles.join(" · ") : "No roles available"}</small></div></div><div className="notice-card"><KeyRound size={17} /><div><strong>User provisioning is not enabled here</strong><p>The mounted backend exposes role listing and current-user information, but no user-management or permission-edit endpoint.</p></div></div></div>
    </Panel>
  </div>;
}
