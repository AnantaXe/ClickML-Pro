import { useEffect, useState } from 'react';
import { Plus, ArrowUpCircle, RefreshCw, Archive, Box } from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';
import StatCard from '../components/StatCard';
import JsonViewer from '../components/JsonViewer';

export default function Registry() {
  const toast = useToast();
  const [models, setModels] = useState([]);
  const [tab, setTab] = useState('list');
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: '',
    version: '1.0.0',
    framework: 'pytorch',
    base_model: '',
    artifact_path: '',
  });

  const refresh = () => {
    api.registryList()
      .then((r) => setModels(r.models || []))
      .catch(() => {});
  };

  useEffect(() => { refresh(); }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const register = async () => {
    if (!form.name) return toast.error('Model name required');
    setLoading(true);
    try {
      await api.registryRegister(form);
      toast.success(`Model "${form.name}" registered`);
      setForm({ name: '', version: '1.0.0', framework: 'pytorch', base_model: '', artifact_path: '' });
      refresh();
      setTab('list');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const viewInfo = async (name) => {
    try {
      const res = await api.registryInfo(name);
      setSelected(res);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const promote = async (name, version) => {
    try {
      await api.registryPromote(name, version, 'production');
      toast.success(`${name} v${version} promoted to production`);
      refresh();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const frameworks = [...new Set(models.map((m) => m.framework))];
  const productionCount = models.filter((m) => m.stage === 'production').length;

  return (
    <>
      <div className="page-header">
        <h2>Model Registry</h2>
        <p>Version, track, and promote model artifacts through the deployment lifecycle.</p>
      </div>

      <div className="stats-grid">
        <StatCard label="Total Models" value={models.length} color="accent" icon={Archive} />
        <StatCard label="Frameworks" value={frameworks.length} sub={frameworks.join(', ') || 'None'} color="cyan" icon={Box} />
        <StatCard label="In Production" value={productionCount} color="green" />
      </div>

      <div className="tabs">
        <button className={`tab-btn${tab === 'list' ? ' active' : ''}`} onClick={() => setTab('list')}>
          Models
        </button>
        <button className={`tab-btn${tab === 'register' ? ' active' : ''}`} onClick={() => setTab('register')}>
          Register New
        </button>
      </div>

      {tab === 'list' && (
        <div className="card">
          <div className="card-header">
            <h3>Registered Models</h3>
            <button className="btn btn-secondary btn-sm" onClick={refresh}>
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Version</th>
                  <th>Framework</th>
                  <th>Stage</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {models.length === 0 && (
                  <tr className="empty-row"><td colSpan={5}>No models registered yet</td></tr>
                )}
                {models.map((m, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, color: 'var(--text)' }}>{m.name}</td>
                    <td><span className="badge badge-blue">{m.version}</span></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '.78rem' }}>{m.framework}</td>
                    <td>
                      <span className={`badge ${m.stage === 'production' ? 'badge-green' : m.stage === 'staging' ? 'badge-yellow' : 'badge-blue'}`}>
                        {m.stage || 'draft'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '.35rem', justifyContent: 'flex-end' }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => viewInfo(m.name)}>
                          Details
                        </button>
                        <button className="btn btn-primary btn-xs" onClick={() => promote(m.name, m.version)}>
                          <ArrowUpCircle size={11} /> Promote
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'register' && (
        <div className="card">
          <div className="card-header"><h3>Register Model</h3></div>
          <div className="form-row">
            <div className="form-group">
              <label>Model Name</label>
              <input type="text" value={form.name} onChange={set('name')} placeholder="my-llama-finetune" />
            </div>
            <div className="form-group">
              <label>Version</label>
              <input type="text" value={form.version} onChange={set('version')} />
            </div>
            <div className="form-group">
              <label>Framework</label>
              <select value={form.framework} onChange={set('framework')}>
                <option value="pytorch">PyTorch</option>
                <option value="tensorflow">TensorFlow</option>
                <option value="onnx">ONNX</option>
                <option value="jax">JAX</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Base Model</label>
              <input type="text" value={form.base_model} onChange={set('base_model')} placeholder="meta-llama/Llama-3.1-8B" />
            </div>
            <div className="form-group">
              <label>Artifact Path</label>
              <input type="text" value={form.artifact_path} onChange={set('artifact_path')} placeholder="s3://bucket/model-artifact" />
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-primary" onClick={register} disabled={loading}>
              {loading ? <span className="spinner" /> : <Plus size={14} />}
              <span>{loading ? 'Registering...' : 'Register Model'}</span>
            </button>
          </div>
        </div>
      )}

      {selected && (
        <div className="card">
          <div className="card-header">
            <h3>Model Details</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => setSelected(null)}>Close</button>
          </div>
          <JsonViewer data={selected} />
        </div>
      )}
    </>
  );
}
