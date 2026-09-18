import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Layers, Archive, Database, Shield, BookOpen,
  ArrowRight, Activity, Server, Cpu, HardDrive,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import api from '../api';

export default function Overview() {
  const [health, setHealth] = useState(null);
  const [modes, setModes] = useState([]);
  const [methods, setMethods] = useState([]);
  const [models, setModels] = useState([]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    api.trainingModes().then((r) => setModes(r.modes || [])).catch(() => {});
    api.quantMethods().then((r) => setMethods(r.methods || [])).catch(() => {});
    api.registryList().then((r) => setModels(r.models || [])).catch(() => {});
  }, []);

  const quickLinks = [
    { to: '/training', label: 'Training', desc: 'Launch fine-tuning and pretraining jobs', icon: Brain, color: 'accent' },
    { to: '/quantization', label: 'Quantization', desc: 'Compress models for deployment', icon: Layers, color: 'cyan' },
    { to: '/registry', label: 'Registry', desc: 'Version and manage model artifacts', icon: Archive, color: 'green' },
    { to: '/data', label: 'Data Engineering', desc: 'Build ETL pipelines and validate data', icon: Database, color: 'yellow' },
    { to: '/governance', label: 'Governance', desc: 'Budget controls and policy enforcement', icon: Shield, color: 'orange' },
    { to: '/notebook', label: 'Notebook', desc: 'Interactive notebook environment', icon: BookOpen, color: 'purple' },
  ];

  return (
    <>
      <div className="page-header">
        <h2>Platform Overview</h2>
        <p>Monitor your ML infrastructure and access key capabilities.</p>
      </div>

      <div className="stats-grid">
        <StatCard
          label="API Status"
          value={health ? 'Healthy' : 'Checking...'}
          sub={health?.version || 'Connecting'}
          color="green"
          icon={Server}
        />
        <StatCard
          label="Training Modes"
          value={modes.length}
          sub="Available pipelines"
          color="accent"
          icon={Cpu}
        />
        <StatCard
          label="Quant Methods"
          value={methods.length}
          sub="Compression engines"
          color="cyan"
          icon={Layers}
        />
        <StatCard
          label="Registry Models"
          value={models.length}
          sub="Registered artifacts"
          color="yellow"
          icon={HardDrive}
        />
      </div>

      <div className="card">
        <div className="card-header">
          <h3><Activity size={15} /> Quick Access</h3>
        </div>
        <div className="quick-links-grid">
          {quickLinks.map(({ to, label, desc, icon: Icon, color }) => (
            <Link key={to} to={to} className="quick-link">
              <span className="quick-link-icon" style={{ background: `var(--${color}-dim, var(--accent-glow))` }}>
                <Icon size={16} style={{ color: `var(--${color})` }} />
              </span>
              <span className="quick-link-label">{label}</span>
              <span className="quick-link-desc">{desc}</span>
              <span className="quick-link-arrow">
                <ArrowRight size={13} />
              </span>
              <span style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 2, background: `var(--${color})` }} />
            </Link>
          ))}
        </div>
      </div>

      {modes.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Training Modes</h3></div>
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
