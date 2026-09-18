import { useEffect, useState } from 'react';
import { DollarSign, Gauge, ShieldCheck, RefreshCw, Shield } from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';
import JsonViewer from '../components/JsonViewer';
import StatCard from '../components/StatCard';

export default function Governance() {
  const toast = useToast();
  const [tab, setTab] = useState('cost');
  const [policies, setPolicies] = useState([]);

  // cost
  const [costForm, setCostForm] = useState({
    type: 'training',
    base_model: 'meta-llama/Llama-3.1-8B',
    mode: 'finetune',
    epochs: 3,
    batch_size: 4,
  });
  const [costResult, setCostResult] = useState(null);
  const [costLoading, setCostLoading] = useState(false);

  // budget
  const [budgetForm, setBudgetForm] = useState({
    entity_id: '',
    limit_usd: 500,
    entity_type: 'org',
    period_days: 30,
  });
  const [budgetResult, setBudgetResult] = useState(null);
  const [budgetLookup, setBudgetLookup] = useState('');
  const [budgetInfo, setBudgetInfo] = useState(null);

  // quota
  const [quotaForm, setQuotaForm] = useState({
    org_id: '',
    gpu_hours_limit: 100,
    max_concurrent_jobs: 4,
  });
  const [quotaLookup, setQuotaLookup] = useState('');
  const [quotaInfo, setQuotaInfo] = useState(null);

  useEffect(() => {
    api.policies().then((r) => setPolicies(r.policies || [])).catch(() => {});
  }, []);

  const estimateCost = async () => {
    setCostLoading(true);
    try {
      const res = await api.costEstimate({
        type: costForm.type,
        base_model: costForm.base_model,
        mode: costForm.mode,
        training: {
          epochs: Number(costForm.epochs),
          batch_size: Number(costForm.batch_size),
        },
      });
      setCostResult(res);
      toast.success('Cost estimated');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setCostLoading(false);
    }
  };

  const setBudget = async () => {
    if (!budgetForm.entity_id) return toast.error('Entity ID required');
    try {
      const res = await api.budgetSet(budgetForm);
      setBudgetResult(res);
      toast.success('Budget set');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const lookupBudget = async () => {
    if (!budgetLookup) return;
    try {
      const res = await api.budgetGet(budgetLookup);
      setBudgetInfo(res);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const setQuota = async () => {
    if (!quotaForm.org_id) return toast.error('Org ID required');
    try {
      await api.quotaSet(quotaForm);
      toast.success('Quota set');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const lookupQuota = async () => {
    if (!quotaLookup) return;
    try {
      const res = await api.quotaGet(quotaLookup);
      setQuotaInfo(res);
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>Governance</h2>
        <p>Cost estimation, budget controls, GPU quota enforcement, and policy management.</p>
      </div>

      <div className="stats-grid">
        <StatCard label="Policies" value={policies.length} sub="Active rules" color="orange" icon={Shield} />
        <StatCard label="Budget Engine" value="Active" color="green" icon={DollarSign} />
        <StatCard label="Quota Engine" value="Active" color="cyan" icon={Gauge} />
      </div>

      <div className="tabs">
        <button className={`tab-btn${tab === 'cost' ? ' active' : ''}`} onClick={() => setTab('cost')}>
          Cost Estimation
        </button>
        <button className={`tab-btn${tab === 'budget' ? ' active' : ''}`} onClick={() => setTab('budget')}>
          Budgets
        </button>
        <button className={`tab-btn${tab === 'quota' ? ' active' : ''}`} onClick={() => setTab('quota')}>
          Quotas
        </button>
        <button className={`tab-btn${tab === 'policies' ? ' active' : ''}`} onClick={() => setTab('policies')}>
          Policies
        </button>
      </div>

      {/* ── Cost ─── */}
      {tab === 'cost' && (
        <div className="card">
          <div className="card-header"><h3><DollarSign size={15} /> Cost Estimation</h3></div>
          <div className="form-row">
            <div className="form-group">
              <label>Job Type</label>
              <select value={costForm.type} onChange={(e) => setCostForm({ ...costForm, type: e.target.value })}>
                <option value="training">Training</option>
                <option value="quantization">Quantization</option>
              </select>
            </div>
            <div className="form-group">
              <label>Base Model</label>
              <input type="text" value={costForm.base_model} onChange={(e) => setCostForm({ ...costForm, base_model: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Mode</label>
              <input type="text" value={costForm.mode} onChange={(e) => setCostForm({ ...costForm, mode: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Epochs</label>
              <input type="number" value={costForm.epochs} onChange={(e) => setCostForm({ ...costForm, epochs: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Batch Size</label>
              <input type="number" value={costForm.batch_size} onChange={(e) => setCostForm({ ...costForm, batch_size: e.target.value })} />
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-primary" onClick={estimateCost} disabled={costLoading}>
              {costLoading ? <span className="spinner" /> : <DollarSign size={14} />}
              <span>Estimate Cost</span>
            </button>
          </div>
          {costResult && <div style={{ marginTop: '1rem' }}><JsonViewer data={costResult} /></div>}
        </div>
      )}

      {/* ── Budget ─── */}
      {tab === 'budget' && (
        <>
          <div className="card">
            <div className="card-header"><h3>Set Budget</h3></div>
            <div className="form-row">
              <div className="form-group">
                <label>Entity ID</label>
                <input type="text" value={budgetForm.entity_id} onChange={(e) => setBudgetForm({ ...budgetForm, entity_id: e.target.value })} placeholder="org-123" />
              </div>
              <div className="form-group">
                <label>Limit (USD)</label>
                <input type="number" value={budgetForm.limit_usd} onChange={(e) => setBudgetForm({ ...budgetForm, limit_usd: Number(e.target.value) })} />
              </div>
              <div className="form-group">
                <label>Period (days)</label>
                <input type="number" value={budgetForm.period_days} onChange={(e) => setBudgetForm({ ...budgetForm, period_days: Number(e.target.value) })} />
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-primary" onClick={setBudget}>Set Budget</button>
            </div>
            {budgetResult && <div style={{ marginTop: '1rem' }}><JsonViewer data={budgetResult} /></div>}
          </div>
          <div className="card">
            <div className="card-header"><h3>Lookup Budget</h3></div>
            <div className="form-row">
              <div className="form-group">
                <label>Entity ID</label>
                <input type="text" value={budgetLookup} onChange={(e) => setBudgetLookup(e.target.value)} placeholder="org-123" />
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={lookupBudget}><RefreshCw size={13} /> Lookup</button>
            </div>
            {budgetInfo && <div style={{ marginTop: '1rem' }}><JsonViewer data={budgetInfo} /></div>}
          </div>
        </>
      )}

      {/* ── Quota ─── */}
      {tab === 'quota' && (
        <>
          <div className="card">
            <div className="card-header"><h3><Gauge size={15} /> Set Quota</h3></div>
            <div className="form-row">
              <div className="form-group">
                <label>Org ID</label>
                <input type="text" value={quotaForm.org_id} onChange={(e) => setQuotaForm({ ...quotaForm, org_id: e.target.value })} placeholder="org-123" />
              </div>
              <div className="form-group">
                <label>GPU Hours Limit</label>
                <input type="number" value={quotaForm.gpu_hours_limit} onChange={(e) => setQuotaForm({ ...quotaForm, gpu_hours_limit: Number(e.target.value) })} />
              </div>
              <div className="form-group">
                <label>Max Concurrent Jobs</label>
                <input type="number" value={quotaForm.max_concurrent_jobs} onChange={(e) => setQuotaForm({ ...quotaForm, max_concurrent_jobs: Number(e.target.value) })} />
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-primary" onClick={setQuota}>Set Quota</button>
            </div>
          </div>
          <div className="card">
            <div className="card-header"><h3>Lookup Quota</h3></div>
            <div className="form-row">
              <div className="form-group">
                <label>Org ID</label>
                <input type="text" value={quotaLookup} onChange={(e) => setQuotaLookup(e.target.value)} placeholder="org-123" />
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={lookupQuota}><RefreshCw size={13} /> Lookup</button>
            </div>
            {quotaInfo && <div style={{ marginTop: '1rem' }}><JsonViewer data={quotaInfo} /></div>}
          </div>
        </>
      )}

      {/* ── Policies ─── */}
      {tab === 'policies' && (
        <div className="card">
          <div className="card-header">
            <h3><ShieldCheck size={15} /> Policies</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => api.policies().then(r => setPolicies(r.policies || []))}>
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
          {policies.length === 0 ? (
            <div className="empty-state">
              <ShieldCheck size={40} className="empty-icon" />
              <h4>No policies defined</h4>
              <p>Policies are managed via the API or configuration.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Type</th><th>Effect</th><th>Details</th></tr>
                </thead>
                <tbody>
                  {policies.map((p, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{p.name || p.id || `Policy ${i + 1}`}</td>
                      <td>{p.type || '—'}</td>
                      <td>
                        <span className={`badge ${p.effect === 'ALLOW' ? 'badge-green' : 'badge-red'}`}>
                          {p.effect || '—'}
                        </span>
                      </td>
                      <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {JSON.stringify(p.conditions || p)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
