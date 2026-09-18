import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Plus, Play, Trash2, ChevronUp, ChevronDown,
  Save, Download, FileText, Code, Type,
  PlayCircle, StopCircle, RotateCcw, FilePlus,
  List, X, Check, Loader,
} from 'lucide-react';
import api from '../api';
import { useToast } from '../components/Toast';

/* ── Markdown renderer (lightweight) ─────────────────────────────────── */
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="nb-inline-code">$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
  return html;
}

/* ── Cell Component ──────────────────────────────────────────────────── */
function NotebookCell({
  cell, index, totalCells, isSelected, onSelect,
  onUpdate, onDelete, onExecute, onMoveUp, onMoveDown,
  onAddAbove, onAddBelow, onToggleType,
  executing,
}) {
  const [editing, setEditing] = useState(cell.source === '');
  const textareaRef = useRef(null);

  const handleKeyDown = useCallback((e) => {
    // Shift+Enter = execute
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault();
      if (cell.cell_type === 'code') onExecute(cell.id);
    }
    // Tab = indent
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      const ta = e.target;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const newVal = ta.value.substring(0, start) + '    ' + ta.value.substring(end);
      onUpdate(cell.id, newVal);
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 4; }, 0);
    }
    // Escape = exit edit
    if (e.key === 'Escape') setEditing(false);
  }, [cell.id, cell.cell_type, onExecute, onUpdate]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current && editing) {
      const ta = textareaRef.current;
      ta.style.height = 'auto';
      ta.style.height = Math.max(ta.scrollHeight, 36) + 'px';
    }
  }, [cell.source, editing]);

  // Double-click markdown to edit
  const handleDoubleClick = () => setEditing(true);
  const handleBlur = () => {
    if (cell.cell_type === 'markdown' && cell.source.trim()) setEditing(false);
  };

  const isCode = cell.cell_type === 'code';

  return (
    <div
      className={`nb-cell ${isSelected ? 'nb-cell-selected' : ''} ${isCode ? 'nb-cell-code' : 'nb-cell-markdown'}`}
      onClick={() => onSelect(index)}
    >
      {/* Gutter */}
      <div className="nb-cell-gutter">
        {isCode && (
          <button
            className="nb-run-btn"
            onClick={(e) => { e.stopPropagation(); onExecute(cell.id); }}
            disabled={executing}
            title="Run cell (Shift+Enter)"
          >
            {executing ? <Loader size={14} className="nb-spin" /> : <Play size={14} />}
          </button>
        )}
        {isCode && (
          <span className="nb-exec-count">
            [{cell.execution_count ?? ' '}]
          </span>
        )}
      </div>

      {/* Cell content */}
      <div className="nb-cell-content">
        {/* Toolbar (visible on hover / selected) */}
        {isSelected && (
          <div className="nb-cell-toolbar">
            <button onClick={() => onToggleType(cell.id)} title="Toggle code/markdown">
              {isCode ? <Type size={13} /> : <Code size={13} />}
            </button>
            <button onClick={() => onMoveUp(cell.id)} disabled={index === 0} title="Move up">
              <ChevronUp size={13} />
            </button>
            <button onClick={() => onMoveDown(cell.id)} disabled={index === totalCells - 1} title="Move down">
              <ChevronDown size={13} />
            </button>
            <button onClick={() => onAddAbove(index)} title="Add cell above">
              <Plus size={13} />
            </button>
            <button onClick={() => onDelete(cell.id)} title="Delete cell">
              <Trash2 size={13} />
            </button>
          </div>
        )}

        {/* Input area */}
        {isCode || editing ? (
          <textarea
            ref={textareaRef}
            className={`nb-source ${isCode ? 'nb-source-code' : 'nb-source-md'}`}
            value={cell.source}
            onChange={(e) => onUpdate(cell.id, e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            placeholder={isCode ? '# Type Python code...' : 'Markdown text...'}
            spellCheck={!isCode}
            autoFocus={editing && !cell.source}
          />
        ) : (
          <div
            className="nb-markdown-render"
            onDoubleClick={handleDoubleClick}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(cell.source) }}
          />
        )}

        {/* Output area */}
        {isCode && cell.outputs && cell.outputs.length > 0 && (
          <div className="nb-outputs">
            {cell.outputs.map((out, oi) => {
              if (out.output_type === 'stream') {
                return (
                  <pre key={oi} className={`nb-output-stream ${out.name === 'stderr' ? 'nb-output-stderr' : ''}`}>
                    {out.text}
                  </pre>
                );
              }
              if (out.output_type === 'error') {
                return (
                  <pre key={oi} className="nb-output-error">
                    {out.ename}: {out.evalue}
                    {out.traceback?.length > 0 && '\n' + out.traceback.join('\n')}
                  </pre>
                );
              }
              return null;
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Notebook Page ──────────────────────────────────────────────── */
export default function Notebook() {
  const toast = useToast();

  // State
  const [notebooks, setNotebooks] = useState([]);
  const [activeNb, setActiveNb] = useState(null);
  const [selectedCell, setSelectedCell] = useState(0);
  const [executingCells, setExecutingCells] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [showList, setShowList] = useState(true);
  const [newName, setNewName] = useState('');

  // Load notebooks list
  const loadList = useCallback(async () => {
    try {
      const res = await api.notebookList();
      setNotebooks(res.notebooks || []);
    } catch { /* empty */ }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // Create notebook
  const createNotebook = async (name) => {
    try {
      const res = await api.notebookCreate({ name: name || 'Untitled' });
      setActiveNb(res.notebook);
      setShowList(false);
      setSelectedCell(0);
      await loadList();
      toast.success('Notebook created');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Open notebook
  const openNotebook = async (id) => {
    try {
      const res = await api.notebookGet(id);
      setActiveNb(res.notebook);
      setShowList(false);
      setSelectedCell(0);
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Save notebook
  const saveNotebook = async () => {
    if (!activeNb) return;
    try {
      const res = await api.notebookSave(activeNb.id, { name: activeNb.name, cells: activeNb.cells });
      setActiveNb(res.notebook);
      toast.success('Saved');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Delete notebook
  const deleteNotebook = async (id) => {
    try {
      await api.notebookDelete(id);
      if (activeNb?.id === id) { setActiveNb(null); setShowList(true); }
      await loadList();
      toast.info('Notebook deleted');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Cell operations
  const updateCell = (cellId, source) => {
    if (!activeNb) return;
    setActiveNb({
      ...activeNb,
      cells: activeNb.cells.map((c) => (c.id === cellId ? { ...c, source } : c)),
    });
  };

  const addCell = (index = null, type = 'code') => {
    if (!activeNb) return;
    const newCell = {
      id: Math.random().toString(36).slice(2, 10),
      cell_type: type,
      source: '',
      outputs: [],
      execution_count: null,
      metadata: {},
    };
    const cells = [...activeNb.cells];
    if (index !== null && index >= 0) {
      cells.splice(index, 0, newCell);
      setSelectedCell(index);
    } else {
      cells.push(newCell);
      setSelectedCell(cells.length - 1);
    }
    setActiveNb({ ...activeNb, cells });
  };

  const deleteCell = (cellId) => {
    if (!activeNb || activeNb.cells.length <= 1) return;
    const cells = activeNb.cells.filter((c) => c.id !== cellId);
    setActiveNb({ ...activeNb, cells });
    setSelectedCell(Math.min(selectedCell, cells.length - 1));
  };

  const moveCell = (cellId, direction) => {
    if (!activeNb) return;
    const cells = [...activeNb.cells];
    const idx = cells.findIndex((c) => c.id === cellId);
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= cells.length) return;
    [cells[idx], cells[newIdx]] = [cells[newIdx], cells[idx]];
    setActiveNb({ ...activeNb, cells });
    setSelectedCell(newIdx);
  };

  const toggleType = (cellId) => {
    if (!activeNb) return;
    setActiveNb({
      ...activeNb,
      cells: activeNb.cells.map((c) =>
        c.id === cellId
          ? { ...c, cell_type: c.cell_type === 'code' ? 'markdown' : 'code', outputs: [], execution_count: null }
          : c
      ),
    });
  };

  // Execute cell
  const executeCell = async (cellId) => {
    if (!activeNb) return;
    const cell = activeNb.cells.find((c) => c.id === cellId);
    if (!cell || cell.cell_type !== 'code' || !cell.source.trim()) return;

    setExecutingCells((prev) => new Set(prev).add(cellId));
    try {
      const res = await api.notebookExecuteCell(activeNb.id, cellId, { source: cell.source });
      setActiveNb((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          cells: prev.cells.map((c) =>
            c.id === cellId ? { ...c, outputs: res.outputs, execution_count: res.execution_count } : c
          ),
        };
      });
      // Auto-advance to next cell
      const idx = activeNb.cells.findIndex((c) => c.id === cellId);
      if (idx < activeNb.cells.length - 1) setSelectedCell(idx + 1);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setExecutingCells((prev) => {
        const next = new Set(prev);
        next.delete(cellId);
        return next;
      });
    }
  };

  // Execute all
  const executeAll = async () => {
    if (!activeNb) return;
    // Must save first
    await saveNotebook();
    setLoading(true);
    try {
      const res = await api.notebookExecuteAll(activeNb.id);
      // Refresh notebook
      const nbRes = await api.notebookGet(activeNb.id);
      setActiveNb(nbRes.notebook);
      toast.success(`Executed ${res.results.length} cells`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Download
  const downloadNotebook = async () => {
    if (!activeNb) return;
    await saveNotebook();
    try {
      const res = await api.notebookDownload(activeNb.id);
      const blob = new Blob([JSON.stringify(res.ipynb, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activeNb.name.replace(/\s/g, '_')}.ipynb`;
      a.click();
      URL.revokeObjectURL(url);
      toast.info('Downloaded .ipynb');
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Clear all outputs
  const clearOutputs = () => {
    if (!activeNb) return;
    setActiveNb({
      ...activeNb,
      cells: activeNb.cells.map((c) => ({ ...c, outputs: [], execution_count: null })),
    });
  };

  // ── Notebook list view ──────────────────────────────────────────────
  if (showList || !activeNb) {
    return (
      <div className="nb-list-view">
        <div className="page-header">
          <h2>Notebook</h2>
          <p>Create and manage interactive notebooks for experimentation and analysis.</p>
        </div>
        <div className="card">
          <div className="card-header">
            <h3><FileText size={15} /> Notebooks</h3>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Notebook name"
                style={{ width: 180 }}
                onKeyDown={(e) => { if (e.key === 'Enter') { createNotebook(newName); setNewName(''); } }}
              />
              <button className="btn btn-primary" onClick={() => { createNotebook(newName); setNewName(''); }}>
                <FilePlus size={14} /> New
              </button>
            </div>
          </div>

          {notebooks.length === 0 ? (
            <div className="empty-state">
              <FileText size={48} className="empty-icon" />
              <h4>No notebooks yet</h4>
              <p>Create a new notebook to get started.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Cells</th><th>Created</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {notebooks.map((nb) => (
                    <tr key={nb.id}>
                      <td>
                        <button
                          className="nb-name-link"
                          onClick={() => openNotebook(nb.id)}
                        >
                          {nb.name}
                        </button>
                      </td>
                      <td>{nb.cell_count}</td>
                      <td style={{ fontSize: '.8rem', color: 'var(--text-muted)' }}>
                        {new Date(nb.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <button className="btn btn-danger btn-sm" onClick={() => deleteNotebook(nb.id)}>
                          <Trash2 size={12} /> Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Notebook editor view ────────────────────────────────────────────
  return (
    <div className="nb-editor">
      {/* Notebook toolbar */}
      <div className="nb-toolbar">
        <div className="nb-toolbar-left">
          <button className="btn btn-secondary btn-sm" onClick={() => { setShowList(true); }} title="Back to list">
            <List size={14} /> All Notebooks
          </button>
          <span className="nb-title">{activeNb.name}</span>
        </div>
        <div className="nb-toolbar-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => addCell(selectedCell + 1, 'code')} title="Add code cell">
            <Plus size={13} /> Code
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => addCell(selectedCell + 1, 'markdown')} title="Add markdown cell">
            <Plus size={13} /> Markdown
          </button>
          <div className="nb-toolbar-sep" />
          <button className="btn btn-primary btn-sm" onClick={executeAll} disabled={loading} title="Run all cells">
            {loading ? <Loader size={13} className="nb-spin" /> : <PlayCircle size={13} />}
            Run All
          </button>
          <button className="btn btn-secondary btn-sm" onClick={clearOutputs} title="Clear all outputs">
            <RotateCcw size={13} />
          </button>
          <div className="nb-toolbar-sep" />
          <button className="btn btn-secondary btn-sm" onClick={saveNotebook} title="Save notebook">
            <Save size={13} />
          </button>
          <button className="btn btn-secondary btn-sm" onClick={downloadNotebook} title="Download .ipynb">
            <Download size={13} />
          </button>
        </div>
      </div>

      {/* Cells */}
      <div className="nb-cells">
        {activeNb.cells.map((cell, i) => (
          <NotebookCell
            key={cell.id}
            cell={cell}
            index={i}
            totalCells={activeNb.cells.length}
            isSelected={selectedCell === i}
            onSelect={setSelectedCell}
            onUpdate={updateCell}
            onDelete={deleteCell}
            onExecute={executeCell}
            onMoveUp={(id) => moveCell(id, -1)}
            onMoveDown={(id) => moveCell(id, 1)}
            onAddAbove={(idx) => addCell(idx, 'code')}
            onAddBelow={(idx) => addCell(idx + 1, 'code')}
            onToggleType={toggleType}
            executing={executingCells.has(cell.id)}
          />
        ))}

        {/* Add cell button at bottom */}
        <div className="nb-add-cell-row">
          <button className="nb-add-cell-btn" onClick={() => addCell(null, 'code')}>
            <Plus size={14} /> Add Cell
          </button>
        </div>
      </div>
    </div>
  );
}
