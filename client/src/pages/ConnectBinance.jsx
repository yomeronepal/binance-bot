import { useEffect, useState } from 'react';
import {
  Shield, AlertTriangle, CheckCircle2, XCircle,
  Copy, Loader2, KeyRound, RefreshCw, Trash2, Link2,
} from 'lucide-react';
import {
  getServerIp, getConnection, connect, revalidate, disconnect,
} from '../services/binanceConnectionService';

const STATUS_LABEL = {
  ACTIVE: 'Active',
  PAUSED: 'Connected (paused)',
  REVOKED: 'Revoked',
  BROKEN: 'Broken',
};

const STATUS_TONE = {
  ACTIVE: 'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300',
  PAUSED: 'bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300',
  REVOKED: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
  BROKEN: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
};

function StatusPill({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_TONE[status] || 'bg-gray-100 text-gray-700'}`}>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

function ServerIpBlock({ ip }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(ip);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable */ }
  };
  return (
    <div className="flex items-center gap-2 bg-gray-900 text-gray-100 px-3 py-2 rounded font-mono text-sm">
      <span>{ip || '…'}</span>
      <button
        type="button"
        onClick={onCopy}
        disabled={!ip}
        className="ml-auto inline-flex items-center gap-1 text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded disabled:opacity-50"
      >
        <Copy className="w-3 h-3" />
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}

function StepInstructions({ ip, confirmed, onConfirmChange, onNext }) {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold flex items-center gap-2 text-gray-900 dark:text-white">
        <Shield className="w-5 h-5" /> Step 1 — Create your Binance API key
      </h2>
      <p className="text-sm text-gray-600 dark:text-gray-400">
        Generate the key on Binance and configure it exactly as below before continuing.
      </p>
      <ol className="list-decimal pl-5 space-y-2 text-sm text-gray-800 dark:text-gray-200">
        <li>Open <span className="font-medium">Binance → Account → API Management</span> and click <span className="font-medium">Create API</span>.</li>
        <li>Pick <span className="font-medium">System generated</span>. Save the <span className="font-medium">Secret</span> — Binance shows it only once.</li>
        <li>Under <span className="font-medium">API restrictions</span>:
          <ul className="list-disc pl-5 mt-1 space-y-1">
            <li className="text-green-700 dark:text-green-400">✅ Enable <span className="font-medium">Futures</span></li>
            <li className="text-red-700 dark:text-red-400">❌ Disable <span className="font-medium">Withdrawals</span></li>
            <li className="text-red-700 dark:text-red-400">❌ Disable <span className="font-medium">Internal Transfer</span></li>
          </ul>
        </li>
        <li>Tick <span className="font-medium">Restrict access to trusted IPs only</span> and add this IP to the allowlist:
          <div className="mt-2"><ServerIpBlock ip={ip} /></div>
        </li>
        <li>Save the API key on Binance, then come back here.</li>
      </ol>

      <div className="bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/20 rounded p-3 text-sm text-amber-900 dark:text-amber-300 flex gap-2">
        <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div>
          <strong>Withdrawal must be disabled.</strong> The bot never needs withdrawal access — leaving it on
          permanently exposes your funds if the key ever leaks. We refuse trading on keys with withdrawals enabled.
        </div>
      </div>

      <label className="flex items-start gap-2 text-sm pt-2 text-gray-800 dark:text-gray-200">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => onConfirmChange(e.target.checked)}
          className="mt-1"
        />
        <span>I have created the API key, allowlisted the IP above, enabled Futures, and disabled both Withdrawals and Internal Transfer.</span>
      </label>

      <div className="flex justify-end pt-2">
        <button
          type="button"
          disabled={!confirmed || !ip}
          onClick={onNext}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded text-sm font-medium"
        >
          Continue
        </button>
      </div>
    </div>
  );
}

function StepKeys({ apiKey, apiSecret, onKeyChange, onSecretChange, onSubmit, submitting, errorBanner, onBack }) {
  const canSubmit = apiKey.trim().length >= 10 && apiSecret.trim().length >= 10 && !submitting;
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (canSubmit) onSubmit(); }}
      className="space-y-4"
    >
      <h2 className="text-lg font-semibold flex items-center gap-2 text-gray-900 dark:text-white">
        <KeyRound className="w-5 h-5" /> Step 2 — Enter your API key
      </h2>
      <p className="text-sm text-gray-600 dark:text-gray-400">
        We will validate the key against Binance and store it encrypted at rest. Trading stays paused until you turn it on later.
      </p>
      {errorBanner && (
        <div className="bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20 text-red-800 dark:text-red-300 rounded px-3 py-2 text-sm">
          {errorBanner}
        </div>
      )}
      <div className="space-y-1">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">API key</label>
        <input
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(e) => onKeyChange(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm font-mono bg-white dark:bg-gray-900 dark:border-gray-700 dark:text-white"
          placeholder="64-character key from Binance"
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">API secret</label>
        <input
          type="password"
          autoComplete="off"
          value={apiSecret}
          onChange={(e) => onSecretChange(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm font-mono bg-white dark:bg-gray-900 dark:border-gray-700 dark:text-white"
          placeholder="Shown only once when you created the key"
        />
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Your secret is encrypted before it touches the database. We never log, display, or share it.
      </p>
      <div className="flex justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white disabled:opacity-50"
        >
          ← Back
        </button>
        <button
          type="submit"
          disabled={!canSubmit}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded text-sm font-medium inline-flex items-center gap-2"
        >
          {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
          Validate & connect
        </button>
      </div>
    </form>
  );
}

function StepResult({ validation, connection, onRetry, onContinueToStatus }) {
  const ok = validation?.ok;
  const code = validation?.code;
  const Icon = ok ? CheckCircle2 : XCircle;
  const tone = ok
    ? (code === 'withdraw_enabled' ? 'text-amber-700 dark:text-amber-400' : 'text-green-700 dark:text-green-400')
    : 'text-red-700 dark:text-red-400';
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold flex items-center gap-2 text-gray-900 dark:text-white">
        <Icon className={`w-5 h-5 ${tone}`} /> Step 3 — Result
      </h2>
      <div className={`text-sm ${tone}`}>{validation?.message}</div>
      {connection && (
        <div className="border rounded p-3 text-sm space-y-1 bg-gray-50 dark:bg-gray-900/50 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-gray-500 dark:text-gray-400 w-32">Status</span>
            <StatusPill status={connection.status} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500 dark:text-gray-400 w-32">API key</span>
            <span className="font-mono text-xs text-gray-900 dark:text-gray-200">{connection.api_key_hint || '—'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500 dark:text-gray-400 w-32">IP allowlist</span>
            <span className="text-gray-900 dark:text-gray-200">{connection.ip_check_passed ? 'OK' : 'Failed / not yet verified'}</span>
          </div>
          {connection.permissions?.canWithdraw && (
            <div className="text-amber-700 dark:text-amber-400">
              ⚠ Withdrawals are enabled on this key. Recommend revoking and re-creating without withdrawals.
            </div>
          )}
        </div>
      )}
      <div className="flex justify-end gap-2 pt-2">
        {!ok && (
          <button
            type="button"
            onClick={onRetry}
            className="text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-200 px-3 py-1.5 rounded inline-flex items-center gap-1"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        )}
        {ok && (
          <button
            type="button"
            onClick={onContinueToStatus}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium"
          >
            Continue
          </button>
        )}
      </div>
    </div>
  );
}

function ConnectionStatus({ connection, busy, onRevalidate, onDisconnect, onReconnect }) {
  const lastChecked = connection.last_check_at
    ? new Date(connection.last_check_at).toLocaleString()
    : '—';
  const needsAttention =
    connection.status === 'BROKEN' || connection.status === 'REVOKED';

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2 text-gray-900 dark:text-white">
            <Link2 className="w-5 h-5" /> Binance account connection
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Auto-trading turns on only after you enable it in Settings (coming soon).
          </p>
        </div>
        <StatusPill status={connection.status} />
      </div>

      {needsAttention && (
        <div className="bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20 rounded p-3 text-sm text-red-800 dark:text-red-300 flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <strong>This connection needs attention.</strong>{' '}
            {connection.last_error || 'Reconnect to restore it.'}
          </div>
        </div>
      )}

      {!needsAttention && connection.permissions?.canWithdraw && (
        <div className="bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/20 rounded p-3 text-sm text-amber-900 dark:text-amber-300 flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <strong>Withdrawals are enabled on this API key.</strong> The bot does not need that permission.
            Revoke this key on Binance, create a new one with withdrawals disabled, and reconnect.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div className="border rounded p-3 dark:border-gray-700">
          <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">API key</div>
          <div className="font-mono mt-1 text-gray-900 dark:text-gray-100">{connection.api_key_hint || '—'}</div>
        </div>
        <div className="border rounded p-3 dark:border-gray-700">
          <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">IP allowlist</div>
          <div className="mt-1 text-gray-900 dark:text-gray-100">{connection.ip_check_passed ? 'Verified' : 'Not verified'}</div>
        </div>
        <div className="border rounded p-3 dark:border-gray-700">
          <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Last health check</div>
          <div className="mt-1 text-gray-900 dark:text-gray-100">{lastChecked}</div>
        </div>
        <div className="border rounded p-3 dark:border-gray-700">
          <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Permissions</div>
          <div className="mt-1 space-x-2">
            <span className={connection.permissions?.canTrade ? 'text-green-700 dark:text-green-400' : 'text-gray-500'}>
              {connection.permissions?.canTrade ? '✓' : '–'} Trade
            </span>
            <span className={connection.permissions?.canWithdraw ? 'text-amber-700 dark:text-amber-400' : 'text-gray-500'}>
              {connection.permissions?.canWithdraw ? '⚠' : '✓'} {connection.permissions?.canWithdraw ? 'Withdraw' : 'No withdraw'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 pt-2">
        <button
          type="button"
          onClick={onRevalidate}
          disabled={busy}
          className="text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-200 px-3 py-1.5 rounded inline-flex items-center gap-1 disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Re-check now
        </button>
        {needsAttention && (
          <button
            type="button"
            onClick={onReconnect}
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded inline-flex items-center gap-1"
          >
            <KeyRound className="w-4 h-4" /> Reconnect
          </button>
        )}
        <button
          type="button"
          onClick={onDisconnect}
          disabled={busy}
          className="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 px-3 py-1.5 rounded inline-flex items-center gap-1 ml-auto disabled:opacity-50"
        >
          <Trash2 className="w-4 h-4" /> Disconnect
        </button>
      </div>
    </div>
  );
}

export default function ConnectBinance() {
  const [serverIp, setServerIp] = useState('');
  const [connection, setConnection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // 'status' = managing existing connection
  // 'wizard' = walking through 3 steps
  const [view, setView] = useState('status');
  const [step, setStep] = useState(1);
  const [confirmed, setConfirmed] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [validation, setValidation] = useState(null);
  const [errorBanner, setErrorBanner] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      // Fire both requests independently — a connection 404 is normal for
      // first-time visitors, but a server-ip failure means the backend
      // doesn't have the new endpoints deployed yet, and we want to
      // surface that distinctly instead of swallowing it in Promise.all.
      const [ipResult, connResult] = await Promise.allSettled([
        getServerIp(),
        getConnection(),
      ]);
      if (!alive) return;

      if (ipResult.status === 'fulfilled') {
        setServerIp(ipResult.value);
      } else {
        const err = ipResult.reason;
        const status = err?.response?.status;
        const msg =
          status === 404
            ? 'Server-IP endpoint not found. The backend has not been redeployed with the latest code yet — run the migration and restart the web container.'
            : err?.message || 'Could not load the server IP.';
        setErrorBanner(msg);
      }

      if (connResult.status === 'fulfilled') {
        setConnection(connResult.value);
        setView(connResult.value ? 'status' : 'wizard');
      } else {
        setView('wizard');
      }

      setLoading(false);
    })();
    return () => { alive = false; };
  }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    setErrorBanner('');
    try {
      const result = await connect({ apiKey, apiSecret });
      setValidation(result.validation);
      const { validation: _ignored, ...rest } = result;
      setConnection(rest);
      setStep(3);
      setApiSecret(''); // wipe from memory regardless of outcome
    } catch (err) {
      const status = err?.response?.status;
      if (status === 429) {
        setErrorBanner('Too many attempts. Wait a few minutes and try again.');
      } else {
        setErrorBanner(err?.response?.data?.detail || err.message || 'Connect failed.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = () => {
    setStep(2);
    setValidation(null);
  };

  const goToWizard = () => {
    setView('wizard');
    setStep(1);
    setConfirmed(false);
    setApiKey('');
    setApiSecret('');
    setValidation(null);
    setErrorBanner('');
  };

  const goToStatus = async () => {
    // Pull fresh state so the status panel reflects the just-validated row.
    setBusy(true);
    try {
      const conn = await getConnection();
      setConnection(conn);
    } finally {
      setBusy(false);
    }
    setView('status');
    setStep(1);
    setConfirmed(false);
    setApiKey('');
    setApiSecret('');
    setValidation(null);
  };

  const handleRevalidate = async () => {
    setBusy(true);
    try {
      const result = await revalidate();
      const { validation: v, ...rest } = result;
      setConnection(rest);
      if (v && !v.ok) {
        // Surface the failure inline instead of redirecting back to the wizard;
        // most failures are transient or fixable from Binance settings.
        setErrorBanner(v.message);
      } else {
        setErrorBanner('');
      }
    } catch (err) {
      setErrorBanner(err?.response?.data?.detail || err.message || 'Re-check failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect your Binance account? This deletes the stored credentials. You can reconnect at any time.')) return;
    setBusy(true);
    try {
      await disconnect();
      setConnection(null);
      setValidation(null);
      goToWizard();
    } catch (err) {
      alert(err?.response?.data?.detail || err.message || 'Disconnect failed.');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-gray-600 dark:text-gray-400">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Connect your Binance account</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Lets us place trades on your account when a signal fires. Auto-trading remains <span className="font-medium">off</span> until you enable it explicitly.
        </p>
      </header>

      {errorBanner && (
        <div className="bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/20 rounded p-3 text-sm text-amber-900 dark:text-amber-300 flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>{errorBanner}</div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-sm p-5">
        {view === 'status' && connection && (
          <ConnectionStatus
            connection={connection}
            busy={busy}
            onRevalidate={handleRevalidate}
            onDisconnect={handleDisconnect}
            onReconnect={goToWizard}
          />
        )}

        {view === 'wizard' && step === 1 && (
          <StepInstructions
            ip={serverIp}
            confirmed={confirmed}
            onConfirmChange={setConfirmed}
            onNext={() => setStep(2)}
          />
        )}
        {view === 'wizard' && step === 2 && (
          <StepKeys
            apiKey={apiKey}
            apiSecret={apiSecret}
            onKeyChange={setApiKey}
            onSecretChange={setApiSecret}
            onSubmit={handleSubmit}
            submitting={submitting}
            errorBanner={errorBanner}
            onBack={() => setStep(1)}
          />
        )}
        {view === 'wizard' && step === 3 && (
          <StepResult
            validation={validation}
            connection={connection}
            onRetry={handleRetry}
            onContinueToStatus={goToStatus}
          />
        )}
      </div>
    </div>
  );
}
