import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Plus, Play, Trash2, Settings, X, Save,
  Database, ArrowRight, Download, Upload,
  CheckCircle, Filter, Bell, GitBranch,
  Loader, ChevronRight, RefreshCw, Rocket,
  FileCode, FolderOpen, Check,
} from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';

/* ── Task type metadata ─────────────────────────────────────────────── */
const TASK_ICONS = {
  extract: Download,
  transform: Filter,
  load: Upload,
  validate: CheckCircle,
  notify: Bell,
  branch: GitBranch,
};

const TASK_COLORS = {
  extract: 'var(--cyan)',
  transform: 'var(--accent)',
  load: 'var(--green)',
  validate: 'var(--yellow)',
  notify: 'var(--orange)',
  branch: 'var(--red)',
};

const STATUS_COLORS = {
  idle: 'var(--text-dim)',
  running: 'var(--accent)',
  success: 'var(--green)',
  failed: 'var(--red)',
};

/* ── Config Field Renderer ──────────────────────────────────────────── */
function ConfigField({ fieldKey, value, onChange }) {
  if (typeof value === 'boolean') {
    return (
      <div className="dag-config-field">
        <label>
          <input type="checkbox" checked={value} onChange={(e) => onChange(fieldKey, e.target.checked)} />
          <span>{fieldKey.replace(/_/g, ' ')}</span>
        </label>
      </div>
    );
  }
  if (Array.isArray(value)) {
    return (
      <div className="dag-config-field">
        <label>{fieldKey.replace(/_/g, ' ')}</label>
        <input
          type="text"
          value={value.join(', ')}
          onChange={(e) => onChange(fieldKey, e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="comma separated"
        />
      </div>
    );
  }
  if (typeof value === 'object' && value !== null) {
    return (
      <div className="dag-config-field">
        <label>{fieldKey.replace(/_/g, ' ')}</label>
        <textarea
          value={JSON.stringify(value, null, 2)}
          onChange={(e) => { try { onChange(fieldKey, JSON.parse(e.target.value)); } catch { /* ignore */ } }}
          rows={3}
        />
      </div>
    );
  }
  if (typeof value === 'number') {
    return (
      <div className="dag-config-field">
        <label>{fieldKey.replace(/_/g, ' ')}</label>
        <input type="number" value={value} onChange={(e) => onChange(fieldKey, Number(e.target.value))} />
      </div>
    );
  }
  // String
  const isLong = String(value).length > 60 || fieldKey === 'query' || fieldKey === 'custom_script' || fieldKey === 'filter_expression';
  return (
    <div className="dag-config-field">
      <label>{fieldKey.replace(/_/g, ' ')}</label>
      {isLong ? (
        <textarea value={value} onChange={(e) => onChange(fieldKey, e.target.value)} rows={3} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(fieldKey, e.target.value)} />
      )}
    </div>
  );
}

/* ── Task Config Panel (slide-in) ───────────────────────────────────── */
function TaskConfigPanel({ task, onClose, onSave, onDelete }) {
  const [config, setConfig] = useState({ ...task.config });
  const [label, setLabel] = useState(task.label);

  const handleFieldChange = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    onSave(task.id, { config, label });
  };

  const Icon = TASK_ICONS[task.type] || Database;
  const color = TASK_COLORS[task.type] || 'var(--text)';

  return (
    <div className="dag-panel-overlay" onClick={onClose}>
      <div className="dag-config-panel" onClick={(e) => e.stopPropagation()}>
        <div className="dag-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon size={18} style={{ color }} />
            <span style={{ fontWeight: 600 }}>{task.type.charAt(0).toUpperCase() + task.type.slice(1)} Task</span>
          </div>
          <button className="dag-panel-close" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="dag-panel-body">
          <div className="dag-config-field">
            <label>Label</label>
            <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>

          <div className="dag-config-section-title">Configuration</div>
          {Object.entries(config).map(([key, val]) => (
            <ConfigField key={key} fieldKey={key} value={val} onChange={handleFieldChange} />
          ))}
        </div>

        <div className="dag-panel-footer">
          <button className="btn btn-primary btn-sm" onClick={handleSave}>
            <Save size={13} /> Save
          </button>
          <button className="btn btn-danger btn-sm" onClick={() => onDelete(task.id)}>
            <Trash2 size={13} /> Delete
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── DAG Canvas (SVG-based flow view) ───────────────────────────────── */
function DAGCanvas({ dag, onTaskClick, onTaskDrag, activeTaskId }) {
  const svgRef = useRef(null);
  const [dragging, setDragging] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e, task) => {
    e.stopPropagation();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    setDragging(task.id);
    setDragOffset({
      x: e.clientX - rect.left - task.position.x,
      y: e.clientY - rect.top - task.position.y,
    });
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragging || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = Math.max(0, e.clientX - rect.left - dragOffset.x);
    const y = Math.max(0, e.clientY - rect.top - dragOffset.y);
    onTaskDrag(dragging, { x, y });
  }, [dragging, dragOffset, onTaskDrag]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  useEffect(() => {
    if (dragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragging, handleMouseMove, handleMouseUp]);

  if (!dag) return null;

  const tasksById = {};
  dag.tasks.forEach((t) => { tasksById[t.id] = t; });

  const BLOCK_W = 180;
  const BLOCK_H = 72;

  // Compute SVG dimensions
  let maxX = 800, maxY = 400;
  dag.tasks.forEach((t) => {
    maxX = Math.max(maxX, t.position.x + BLOCK_W + 60);
    maxY = Math.max(maxY, t.position.y + BLOCK_H + 60);
  });

  return (
    <svg
      ref={svgRef}
      className="dag-canvas"
      width="100%"
      height={maxY}
      viewBox={`0 0 ${maxX} ${maxY}`}
      style={{ minHeight: 300 }}
    >
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="var(--text-dim)" />
        </marker>
        <marker id="arrow-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="var(--accent)" />
        </marker>
      </defs>

      {/* Grid */}
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--border)" strokeWidth="0.5" opacity="0.3" />
      </pattern>
      <rect width="100%" height="100%" fill="url(#grid)" />

      {/* Edges */}
      {dag.edges.map((edge) => {
        const src = tasksById[edge.source];
        const tgt = tasksById[edge.target];
        if (!src || !tgt) return null;

        const x1 = src.position.x + BLOCK_W;
        const y1 = src.position.y + BLOCK_H / 2;
        const x2 = tgt.position.x;
        const y2 = tgt.position.y + BLOCK_H / 2;

        // Bezier curve
        const midX = (x1 + x2) / 2;
        const path = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;

        const isActive = activeTaskId === edge.source || activeTaskId === edge.target;

        return (
          <g key={edge.id}>
            <path
              d={path}
              fill="none"
              stroke={isActive ? 'var(--accent)' : 'var(--text-dim)'}
              strokeWidth={isActive ? 2.5 : 1.5}
              strokeDasharray={isActive ? 'none' : '6 3'}
              markerEnd={isActive ? 'url(#arrow-active)' : 'url(#arrow)'}
              style={{ transition: 'all 0.2s' }}
            />
          </g>
        );
      })}

      {/* Task blocks */}
      {dag.tasks.map((task) => {
        const Icon = TASK_ICONS[task.type] || Database;
        const color = TASK_COLORS[task.type] || 'var(--text)';
        const statusColor = STATUS_COLORS[task.status] || STATUS_COLORS.idle;
        const isActive = activeTaskId === task.id;

        return (
          <g
            key={task.id}
            transform={`translate(${task.position.x}, ${task.position.y})`}
            style={{ cursor: dragging === task.id ? 'grabbing' : 'grab' }}
            onMouseDown={(e) => handleMouseDown(e, task)}
            onClick={(e) => { e.stopPropagation(); onTaskClick(task); }}
          >
            {/* Block shadow */}
            <rect
              x={2} y={2} width={BLOCK_W} height={BLOCK_H} rx={10}
              fill="rgba(0,0,0,0.3)" opacity={0.5}
            />
            {/* Block body */}
            <rect
              x={0} y={0} width={BLOCK_W} height={BLOCK_H} rx={10}
              fill="var(--surface-2)"
              stroke={isActive ? color : 'var(--border)'}
              strokeWidth={isActive ? 2.5 : 1}
              style={{ transition: 'all 0.2s' }}
            />
            {/* Color accent bar */}
            <rect x={0} y={0} width={5} height={BLOCK_H} rx={3} fill={color} />
            {/* Status dot */}
            <circle cx={BLOCK_W - 14} cy={14} r={4} fill={statusColor} />
            {/* Icon */}
            <foreignObject x={16} y={14} width={24} height={24}>
              <Icon size={20} color={color} />
            </foreignObject>
            {/* Label */}
            <text x={44} y={30} fill="var(--text)" fontSize="13" fontWeight="600" fontFamily="Inter, system-ui, sans-serif">
              {task.label}
            </text>
            {/* Type subtitle */}
            <text x={44} y={50} fill="var(--text-muted)" fontSize="10" fontFamily="Inter, system-ui, sans-serif" textTransform="uppercase">
              {task.type}
            </text>
            {/* Settings icon */}
            <foreignObject x={BLOCK_W - 30} y={BLOCK_H - 26} width={20} height={20}>
              <Settings size={14} color="var(--text-dim)" style={{ cursor: 'pointer' }} />
            </foreignObject>
          </g>
        );
      })}
    </svg>
  );
}

/* ── Main Data Engineering Page ──────────────────────────────────────── */
export default function DataEngineering() {
  const toast = useToast();
  const [tab, setTab] = useState('pipelines');

  // DAG state
  const [dags, setDags] = useState([]);
  const [activeDag, setActiveDag] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [showPanel, setShowPanel] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [dagName, setDagName] = useState('');
  const [deploying, setDeploying] = useState(false);
  const [deployResult, setDeployResult] = useState(null);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deployDir, setDeployDir] = useState('~/airflow/dags');
  const [exporting, setExporting] = useState(false);

  // Load DAGs and templates
  const loadDags = useCallback(async () => {
    try {
      const res = await api.airflowListDags();
      setDags(res.dags || []);
    } catch { /* empty */ }
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      const res = await api.airflowTaskTemplates();
      setTemplates(res.templates || []);
    } catch { /* empty */ }
  }, []);

  useEffect(() => { loadDags(); loadTemplates(); }, [loadDags, loadTemplates]);

  // Create ETL DAG
  const createETL = async () => {
    try {
      const res = await api.airflowCreateEtl({ name: dagName || 'ETL Pipeline' });
      setActiveDag(res.dag);
      setDagName('');
      await loadDags();
      toast.success('ETL pipeline created');
    } catch (err) { toast.error(err.message); }
  };

  const createEmptyDag = async () => {
    try {
      const res = await api.airflowCreateDag({ name: dagName || 'New Pipeline' });
      setActiveDag(res.dag);
      setDagName('');
      await loadDags();
      toast.success('Pipeline created');
    } catch (err) { toast.error(err.message); }
  };

  const openDag = async (id) => {
    try {
      const res = await api.airflowGetDag(id);
      setActiveDag(res.dag);
      setRunResult(null);
    } catch (err) { toast.error(err.message); }
  };

  const deleteDag = async (id) => {
    try {
      await api.airflowDeleteDag(id);
      if (activeDag?.id === id) setActiveDag(null);
      await loadDags();
      toast.info('Pipeline deleted');
    } catch (err) { toast.error(err.message); }
  };

  // Add task
  const addTask = async (taskType) => {
    if (!activeDag) return;
    // Auto-position: place right of last task
    const lastTask = activeDag.tasks[activeDag.tasks.length - 1];
    const pos = lastTask
      ? { x: lastTask.position.x + 250, y: lastTask.position.y }
      : { x: 100, y: 150 };

    try {
      const res = await api.airflowAddTask(activeDag.id, { task: { task_type: taskType, position: pos } });
      const updatedDag = { ...activeDag, tasks: [...activeDag.tasks, res.task] };

      // Auto-connect to last task
      if (lastTask) {
        try {
          const edgeRes = await api.airflowAddEdge(activeDag.id, { source_id: lastTask.id, target_id: res.task.id });
          if (edgeRes.edge) {
            updatedDag.edges = [...activeDag.edges, edgeRes.edge];
          }
        } catch { /* ignore edge errors */ }
      }

      setActiveDag(updatedDag);
    } catch (err) { toast.error(err.message); }
  };

  // Update task config
  const updateTask = async (taskId, updates) => {
    if (!activeDag) return;
    try {
      const res = await api.airflowUpdateTask(activeDag.id, taskId, updates);
      setActiveDag({
        ...activeDag,
        tasks: activeDag.tasks.map((t) => (t.id === taskId ? res.task : t)),
      });
      setShowPanel(false);
      toast.success('Task updated');
    } catch (err) { toast.error(err.message); }
  };

  // Delete task
  const deleteTask = async (taskId) => {
    if (!activeDag) return;
    try {
      await api.airflowDeleteTask(activeDag.id, taskId);
      setActiveDag({
        ...activeDag,
        tasks: activeDag.tasks.filter((t) => t.id !== taskId),
        edges: activeDag.edges.filter((e) => e.source !== taskId && e.target !== taskId),
      });
      setShowPanel(false);
      toast.info('Task removed');
    } catch (err) { toast.error(err.message); }
  };

  // Drag task (local only, save on drop)
  const handleTaskDrag = useCallback((taskId, newPos) => {
    setActiveDag((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        tasks: prev.tasks.map((t) =>
          t.id === taskId ? { ...t, position: newPos } : t
        ),
      };
    });
  }, []);

  // Task click
  const handleTaskClick = (task) => {
    setSelectedTask(task);
    setShowPanel(true);
  };

  // Run DAG
  const runDag = async () => {
    if (!activeDag) return;
    setLoading(true);
    setRunResult(null);
    try {
      const res = await api.airflowRunDag(activeDag.id);
      setRunResult(res.run);

      // Update task statuses
      const statusMap = {};
      (res.run.tasks || []).forEach((tr) => { statusMap[tr.task_id] = tr.status; });
      setActiveDag((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          tasks: prev.tasks.map((t) => ({ ...t, status: statusMap[t.id] || t.status })),
        };
      });

      toast.success('Pipeline executed');
    } catch (err) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  // Download DAG as Python file
  const downloadDag = async () => {
    if (!activeDag) return;
    setExporting(true);
    try {
      const res = await api.airflowExportDag(activeDag.id);
      const blob = new Blob([res.content], { type: 'text/x-python' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${res.filename}`);
    } catch (err) { toast.error(err.message); }
    finally { setExporting(false); }
  };

  // Deploy DAG to Airflow
  const deployDag = async () => {
    if (!activeDag) return;
    setDeploying(true);
    setDeployResult(null);
    try {
      const body = deployDir ? { dags_dir: deployDir } : {};
      const res = await api.airflowDeployDag(activeDag.id, body);
      setDeployResult(res);
      toast.success(`Deployed to ${res.path}`);
    } catch (err) {
      toast.error(err.message);
      setDeployResult({ status: 'failed', error: err.message });
    }
    finally { setDeploying(false); }
  };

  // ── Data validation / lineage (keep the original functionality) ─────
  const [vForm, setVForm] = useState({ engine: 'pandas', source_path: '' });
  const [vResult, setVResult] = useState(null);
  const [vLoading, setVLoading] = useState(false);
  const [lForm, setLForm] = useState({ node_id: '', direction: 'downstream' });
  const [lResult, setLResult] = useState(null);
  const [lLoading, setLLoading] = useState(false);

  const validate = async () => {
    if (!vForm.source_path) return toast.error('Source path required');
    setVLoading(true);
    try {
      const res = await api.dataValidate(vForm);
      setVResult(res);
      toast.success('Validation complete');
    } catch (err) { toast.error(err.message); }
    finally { setVLoading(false); }
  };

  const lineage = async () => {
    if (!lForm.node_id) return toast.error('Node ID required');
    setLLoading(true);
    try {
      const res = await api.dataLineage(lForm);
      setLResult(res);
      toast.success('Lineage fetched');
    } catch (err) { toast.error(err.message); }
    finally { setLLoading(false); }
  };

  return (
    <>
      <div className="page-header">
        <h2>Data Engineering</h2>
        <p>Build ETL pipelines, validate datasets, and trace data lineage across your workflows.</p>
      </div>

      <div className="tabs">
        <button className={`tab-btn${tab === 'pipelines' ? ' active' : ''}`} onClick={() => setTab('pipelines')}>
          ETL Pipelines
        </button>
        <button className={`tab-btn${tab === 'validate' ? ' active' : ''}`} onClick={() => setTab('validate')}>
          Validate
        </button>
        <button className={`tab-btn${tab === 'lineage' ? ' active' : ''}`} onClick={() => setTab('lineage')}>
          Lineage
        </button>
      </div>

      {/* ── ETL Pipelines ─────────────────────────────────────────────── */}
      {tab === 'pipelines' && !activeDag && (
        <div className="card">
          <div className="card-header">
            <h3><Database size={15} /> ETL Pipelines</h3>
            <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={dagName}
                onChange={(e) => setDagName(e.target.value)}
                placeholder="Pipeline name"
                style={{ width: 180 }}
              />
              <button className="btn btn-primary btn-sm" onClick={createETL}>
                <Plus size={13} /> ETL Template
              </button>
              <button className="btn btn-secondary btn-sm" onClick={createEmptyDag}>
                <Plus size={13} /> Empty
              </button>
            </div>
          </div>

          {dags.length === 0 ? (
            <div className="empty-state">
              <Database size={48} className="empty-icon" />
              <h4>No pipelines yet</h4>
              <p>Create an ETL pipeline to get started with Airflow-style data workflows.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Tasks</th><th>Schedule</th><th>Created</th><th style={{ width: 80 }}>Actions</th></tr>
                </thead>
                <tbody>
                  {dags.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <button className="nb-name-link" onClick={() => openDag(d.id)}>
                          {d.name}
                        </button>
                      </td>
                      <td>{d.task_count}</td>
                      <td style={{ fontSize: '.8rem', color: 'var(--text-muted)' }}>
                        {d.schedule || 'Manual'}
                      </td>
                      <td style={{ fontSize: '.8rem', color: 'var(--text-muted)' }}>
                        {new Date(d.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '.3rem' }}>
                          <button className="btn btn-secondary btn-xs" onClick={() => openDag(d.id)} title="Open">
                            <Settings size={11} />
                          </button>
                          <button className="btn btn-danger btn-xs" onClick={() => deleteDag(d.id)} title="Delete">
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Pipeline DAG Editor ───────────────────────────────────────── */}
      {tab === 'pipelines' && activeDag && (
        <>
          <div className="dag-toolbar">
            <div className="dag-toolbar-left">
              <button className="btn btn-secondary btn-sm" onClick={() => { setActiveDag(null); loadDags(); }}>
                <ChevronRight size={13} style={{ transform: 'rotate(180deg)' }} /> All Pipelines
              </button>
              <span style={{ fontWeight: 600, marginLeft: '.5rem' }}>{activeDag.name}</span>
              <span className="badge badge-cyan" style={{ marginLeft: '.5rem' }}>{activeDag.tasks.length} tasks</span>
            </div>
            <div className="dag-toolbar-actions">
              {/* Task palette */}
              {templates.map((t) => {
                const Icon = TASK_ICONS[t.type] || Database;
                return (
                  <button
                    key={t.type}
                    className="btn btn-secondary btn-sm"
                    onClick={() => addTask(t.type)}
                    title={t.description}
                  >
                    <Icon size={13} /> {t.label}
                  </button>
                );
              })}
              <div className="nb-toolbar-sep" />
              <button className="btn btn-secondary btn-sm" onClick={downloadDag} disabled={exporting} title="Download as Airflow DAG Python file">
                {exporting ? <Loader size={13} className="nb-spin" /> : <Download size={13} />}
                Download
              </button>
              <button
                className="btn btn-sm"
                style={{ background: 'var(--green-dim)', color: 'var(--green)', border: '1px solid rgba(16,185,129,.2)' }}
                onClick={() => { setShowDeployModal(true); setDeployResult(null); }}
                title="Deploy to Apache Airflow"
              >
                <Rocket size={13} /> Deploy
              </button>
              <div className="nb-toolbar-sep" />
              <button className="btn btn-primary btn-sm" onClick={runDag} disabled={loading}>
                {loading ? <Loader size={13} className="nb-spin" /> : <Play size={13} />}
                Run Pipeline
              </button>
            </div>
          </div>

          {/* Canvas */}
          <div className="dag-canvas-wrap">
            <DAGCanvas
              dag={activeDag}
              onTaskClick={handleTaskClick}
              onTaskDrag={handleTaskDrag}
              activeTaskId={selectedTask?.id}
            />
          </div>

          {/* Run results */}
          {runResult && (
            <div className="card" style={{ marginTop: '1rem' }}>
              <div className="card-header">
                <h3>Pipeline Run Results</h3>
                <span className="badge badge-green">{runResult.status}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Task</th><th>Type</th><th>Status</th><th>Duration</th></tr></thead>
                  <tbody>
                    {runResult.tasks.map((tr) => (
                      <tr key={tr.task_id}>
                        <td>{tr.label}</td>
                        <td><span className="badge badge-blue">{tr.type}</span></td>
                        <td><span className={`badge ${tr.status === 'success' ? 'badge-green' : 'badge-red'}`}>{tr.status}</span></td>
                        <td>{tr.duration_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Deploy to Airflow modal */}
          {showDeployModal && (
            <div className="dag-panel-overlay" onClick={() => setShowDeployModal(false)}>
              <div
                className="dag-config-panel"
                onClick={(e) => e.stopPropagation()}
                style={{ width: 440 }}
              >
                <div className="dag-panel-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Rocket size={18} style={{ color: 'var(--green)' }} />
                    <span style={{ fontWeight: 600 }}>Deploy to Apache Airflow</span>
                  </div>
                  <button className="dag-panel-close" onClick={() => setShowDeployModal(false)}>
                    <X size={16} />
                  </button>
                </div>

                <div className="dag-panel-body">
                  <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontSize: '.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      This will generate an Airflow-compatible DAG Python file and write it to the specified directory.
                      Airflow will automatically detect and schedule the DAG.
                    </p>
                  </div>

                  <div className="dag-config-field">
                    <label><FileCode size={13} /> Pipeline</label>
                    <input type="text" value={activeDag.name} disabled style={{ opacity: .7 }} />
                  </div>

                  <div className="dag-config-field">
                    <label><FolderOpen size={13} /> Airflow DAGs Directory</label>
                    <input
                      type="text"
                      value={deployDir}
                      onChange={(e) => setDeployDir(e.target.value)}
                      placeholder="~/airflow/dags"
                    />
                    <div className="form-help">Path where Airflow scans for DAG files. Set via CLICKML_AIRFLOW_DAGS_DIR env var.</div>
                  </div>

                  <div className="dag-config-field">
                    <label>Tasks</label>
                    <div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap' }}>
                      {activeDag.tasks.map((t) => {
                        const Icon = TASK_ICONS[t.type] || Database;
                        const color = TASK_COLORS[t.type] || 'var(--text)';
                        return (
                          <span key={t.id} className="badge" style={{ background: `color-mix(in srgb, ${color} 12%, transparent)`, color, gap: '.25rem', display: 'inline-flex', alignItems: 'center' }}>
                            <Icon size={10} /> {t.label}
                          </span>
                        );
                      })}
                    </div>
                  </div>

                  {/* Deploy result */}
                  {deployResult && deployResult.status === 'deployed' && (
                    <div style={{
                      marginTop: '1rem',
                      padding: '.75rem',
                      background: 'var(--green-dim)',
                      border: '1px solid rgba(16,185,129,.2)',
                      borderRadius: 'var(--radius-sm)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginBottom: '.4rem' }}>
                        <Check size={14} style={{ color: 'var(--green)' }} />
                        <span style={{ fontWeight: 600, fontSize: '.8rem', color: 'var(--green)' }}>Deployed successfully</span>
                      </div>
                      <div style={{ fontSize: '.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {deployResult.path}
                      </div>
                      <div style={{ fontSize: '.7rem', color: 'var(--text-muted)', marginTop: '.25rem' }}>
                        {deployResult.deployed_at}
                      </div>
                    </div>
                  )}

                  {deployResult && deployResult.status === 'failed' && (
                    <div style={{
                      marginTop: '1rem',
                      padding: '.75rem',
                      background: 'var(--red-dim)',
                      border: '1px solid rgba(239,68,68,.2)',
                      borderRadius: 'var(--radius-sm)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginBottom: '.25rem' }}>
                        <X size={14} style={{ color: 'var(--red)' }} />
                        <span style={{ fontWeight: 600, fontSize: '.8rem', color: 'var(--red)' }}>Deployment failed</span>
                      </div>
                      <div style={{ fontSize: '.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                        {deployResult.error}
                      </div>
                    </div>
                  )}
                </div>

                <div className="dag-panel-footer" style={{ justifyContent: 'space-between' }}>
                  <button className="btn btn-secondary btn-sm" onClick={downloadDag} disabled={exporting}>
                    {exporting ? <Loader size={13} className="nb-spin" /> : <Download size={13} />}
                    Download .py
                  </button>
                  <button
                    className="btn btn-sm"
                    style={{ background: 'var(--green)', color: '#fff', boxShadow: '0 1px 3px rgba(16,185,129,.3)' }}
                    onClick={deployDag}
                    disabled={deploying || !deployDir.trim()}
                  >
                    {deploying ? <Loader size={13} className="nb-spin" /> : <Rocket size={13} />}
                    {deploying ? 'Deploying...' : 'Deploy to Airflow'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Task config panel */}
          {showPanel && selectedTask && (
            <TaskConfigPanel
              task={selectedTask}
              onClose={() => setShowPanel(false)}
              onSave={updateTask}
              onDelete={deleteTask}
            />
          )}
        </>
      )}

      {/* ── Validate ─────────────────────────────────────────────────── */}
      {tab === 'validate' && (
        <div className="card">
          <div className="card-header"><h3>Data Validation</h3></div>
          <div className="form-row">
            <div className="form-group">
              <label>Engine</label>
              <select value={vForm.engine} onChange={(e) => setVForm({ ...vForm, engine: e.target.value })}>
                <option value="pandas">Pandas</option>
                <option value="polars">Polars</option>
                <option value="duckdb">DuckDB</option>
              </select>
            </div>
            <div className="form-group">
              <label>Source Path</label>
              <input
                type="text"
                value={vForm.source_path}
                onChange={(e) => setVForm({ ...vForm, source_path: e.target.value })}
                placeholder="./data/dataset.csv"
              />
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-primary" onClick={validate} disabled={vLoading}>
              {vLoading ? <span className="spinner" /> : <CheckCircle size={14} />}
              <span>{vLoading ? 'Validating...' : 'Validate'}</span>
            </button>
          </div>
          {vResult && (
            <div style={{ marginTop: '1rem' }}>
              <pre className="json-view">{JSON.stringify(vResult, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* ── Lineage ──────────────────────────────────────────────────── */}
      {tab === 'lineage' && (
        <div className="card">
          <div className="card-header"><h3>Data Lineage</h3></div>
          <div className="form-row">
            <div className="form-group">
              <label>Node ID</label>
              <input
                type="text"
                value={lForm.node_id}
                onChange={(e) => setLForm({ ...lForm, node_id: e.target.value })}
                placeholder="dataset_raw_sales"
              />
            </div>
            <div className="form-group">
              <label>Direction</label>
              <select value={lForm.direction} onChange={(e) => setLForm({ ...lForm, direction: e.target.value })}>
                <option value="downstream">Downstream</option>
                <option value="upstream">Upstream</option>
              </select>
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-primary" onClick={lineage} disabled={lLoading}>
              {lLoading ? <span className="spinner" /> : <GitBranch size={14} />}
              <span>{lLoading ? 'Fetching...' : 'Query Lineage'}</span>
            </button>
          </div>
          {lResult && (
            <div style={{ marginTop: '1rem' }}>
              <pre className="json-view">{JSON.stringify(lResult, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </>
  );
}
