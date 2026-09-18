import { useEffect, useState } from 'react';
import { Zap, Layers } from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';
import JsonViewer from '../components/JsonViewer';
import StatCard from '../components/StatCard';

export default function Quantization() {
  const toast = useToast();
  const [methods, setMethods] = useState([]);
  const [form, setForm] = useState({
    model_path: '',
    output_dir: './quantized',
    selected: ['int8'],
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.quantMethods().then((r) => setMethods(r.methods || [])).catch(() => {});
  }, []);

  const toggleMethod = (id) => {
    setForm((prev) => ({
      ...prev,
      selected: prev.selected.includes(id)
        ? prev.selected.filter((m) => m !== id)
        : [...prev.selected, id],
    }));
  };

  const submit = async () => {
    if (!form.model_path) return toast.error('Model path is required');
    if (form.selected.length === 0) return toast.error('Select at least one method');
    setLoading(true);
    setResult(null);
    try {
      const res = await api.quantRun({
        model_path: form.model_path,
        output_dir: form.output_dir,
        methods: form.selected,
      });
      setResult(res);
      toast.success('Quantization complete');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>Model Quantization</h2>
        <p>Compress models using INT8, INT4/NF4, AWQ, GPTQ, GGUF, and ONNX for efficient deployment.</p>
      </div>

      <div className="stats-grid">
        <StatCard label="Available Methods" value={methods.length} sub="Compression engines" color="cyan" icon={Layers} />
        <StatCard label="Selected" value={form.selected.length} sub="Methods to run" color="accent" icon={Zap} />
      </div>

      <div className="card">
        <div className="card-header"><h3>Run Quantization</h3></div>
        <div className="form-row">
          <div className="form-group">
            <label>Model Path</label>
            <input
              type="text"
              value={form.model_path}
              onChange={(e) => setForm({ ...form, model_path: e.target.value })}
              placeholder="./models/my-model or HuggingFace ID"
            />
          </div>
          <div className="form-group">
            <label>Output Directory</label>
            <input
              type="text"
              value={form.output_dir}
              onChange={(e) => setForm({ ...form, output_dir: e.target.value })}
            />
          </div>
        </div>

        <div className="card-section-title">Quantization Methods</div>

        <div className="form-group">
          <div className="checkbox-group">
            {methods.map((m) => (
              <label key={m.id}>
                <input
                  type="checkbox"
                  checked={form.selected.includes(m.id)}
                  onChange={() => toggleMethod(m.id)}
                />
                {m.id}
              </label>
            ))}
          </div>
        </div>

        <div className="form-actions">
          <button className="btn btn-primary" onClick={submit} disabled={loading}>
            {loading ? <span className="spinner" /> : <Zap size={14} />}
            <span>{loading ? 'Processing...' : 'Run Quantization'}</span>
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-header"><h3>Quantization Result</h3></div>
          <JsonViewer data={result} />
        </div>
      )}

      {methods.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Method Reference</h3></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Method</th><th>Description</th></tr></thead>
              <tbody>
                {methods.map((m) => (
                  <tr key={m.id}>
                    <td><span className="badge badge-cyan">{m.id}</span></td>
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
