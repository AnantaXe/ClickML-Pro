import { useEffect, useState } from 'react';
import { Play, Brain } from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';
import JsonViewer from '../components/JsonViewer';
import StatCard from '../components/StatCard';

const defaults = {
  base_model: 'meta-llama/Llama-3.1-8B',
  mode: 'finetune',
  dataset: '',
  epochs: 3,
  batch_size: 4,
  lr: 2e-5,
  output_dir: './output',
};

export default function Training() {
  const toast = useToast();
  const [modes, setModes] = useState([]);
  const [form, setForm] = useState(defaults);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.trainingModes().then((r) => setModes(r.modes || [])).catch(() => {});
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async () => {
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        base_model: form.base_model,
        mode: form.mode,
        dataset: form.dataset,
        output_dir: form.output_dir,
        training: {
          epochs: Number(form.epochs),
          batch_size: Number(form.batch_size),
          lr: Number(form.lr),
        },
      };
      const res = await api.trainingRun(payload);
      setResult(res);
      toast.success('Training job submitted');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>Model Training</h2>
        <p>Configure and launch training jobs across multiple modes including fine-tuning, pretraining, LoRA/PEFT, SFT, and RLHF.</p>
      </div>

      <div className="stats-grid">
        <StatCard label="Available Modes" value={modes.length} color="accent" icon={Brain} />
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Launch Training Job</h3>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Base Model</label>
            <input type="text" value={form.base_model} onChange={set('base_model')} placeholder="e.g. meta-llama/Llama-3.1-8B" />
          </div>
          <div className="form-group">
            <label>Training Mode</label>
            <select value={form.mode} onChange={set('mode')}>
              {modes.map((m) => (
                <option key={m.id} value={m.id}>{m.id} -- {m.description}</option>
              ))}
              {modes.length === 0 && <option value="finetune">finetune</option>}
            </select>
          </div>
          <div className="form-group">
            <label>Dataset</label>
            <input type="text" value={form.dataset} onChange={set('dataset')} placeholder="Path or HuggingFace dataset ID" />
          </div>
        </div>

        <div className="card-section-title">Hyperparameters</div>

        <div className="form-row">
          <div className="form-group">
            <label>Epochs</label>
            <input type="number" value={form.epochs} onChange={set('epochs')} min="1" />
          </div>
          <div className="form-group">
            <label>Batch Size</label>
            <input type="number" value={form.batch_size} onChange={set('batch_size')} min="1" />
          </div>
          <div className="form-group">
            <label>Learning Rate</label>
            <input type="text" value={form.lr} onChange={set('lr')} />
          </div>
          <div className="form-group">
            <label>Output Directory</label>
            <input type="text" value={form.output_dir} onChange={set('output_dir')} />
          </div>
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" onClick={submit} disabled={loading}>
            {loading ? <span className="spinner" /> : <Play size={14} />}
            <span>{loading ? 'Submitting...' : 'Start Training'}</span>
          </button>
          <button className="btn btn-secondary" onClick={() => setForm(defaults)} disabled={loading}>
            Reset
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-header"><h3>Training Result</h3></div>
          <JsonViewer data={result} />
        </div>
      )}

      {modes.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Available Modes</h3></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Mode</th><th>Description</th></tr></thead>
              <tbody>
                {modes.map((m) => (
                  <tr key={m.id}>
                    <td><span className="badge badge-blue">{m.id}</span></td>
                    <td>{m.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
