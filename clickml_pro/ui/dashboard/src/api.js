/**
 * ClickML Pro — API client.
 * All calls go to the FastAPI backend proxied by Vite in dev,
 * or served from the same origin in production.
 */

const BASE = '';

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

const api = {
  // Health
  health: () => request('GET', '/health'),

  // Training
  trainingModes: () => request('GET', '/api/v1/training/modes'),
  trainingRun: (data) => request('POST', '/api/v1/training/run', data),

  // Quantization
  quantMethods: () => request('GET', '/api/v1/quantization/methods'),
  quantRun: (data) => request('POST', '/api/v1/quantization/run', data),

  // Registry
  registryList: () => request('GET', '/api/v1/registry/list'),
  registryInfo: (name) => request('GET', `/api/v1/registry/info/${encodeURIComponent(name)}`),
  registryRegister: (data) => request('POST', '/api/v1/registry/register', data),
  registryPromote: (name, version, stage) =>
    request('POST', `/api/v1/registry/promote/${encodeURIComponent(name)}/${encodeURIComponent(version)}?stage=${stage}`),

  // Data
  dataValidate: (data) => request('POST', '/api/v1/data/validate', data),
  dataLineage: (data) => request('POST', '/api/v1/data/lineage', data),
  dataPipelineRun: (data) => request('POST', '/api/v1/data/pipeline/run', data),

  // Governance
  costEstimate: (data) => request('POST', '/api/v1/governance/cost/estimate', data),
  budgetSet: (data) => request('POST', '/api/v1/governance/budget/set', data),
  budgetGet: (id) => request('GET', `/api/v1/governance/budget/${encodeURIComponent(id)}`),
  quotaSet: (data) => request('POST', '/api/v1/governance/quota/set', data),
  quotaGet: (id, hours = 0) => request('GET', `/api/v1/governance/quota/${encodeURIComponent(id)}?hours=${hours}`),
  policies: () => request('GET', '/api/v1/governance/policies'),

  // Notebook — CRUD
  notebookList: () => request('GET', '/api/v1/notebook/list'),
  notebookCreate: (data) => request('POST', '/api/v1/notebook/create', data),
  notebookGet: (id) => request('GET', `/api/v1/notebook/get/${id}`),
  notebookSave: (id, data) => request('PUT', `/api/v1/notebook/save/${id}`, data),
  notebookDelete: (id) => request('DELETE', `/api/v1/notebook/delete/${id}`),

  // Notebook — Cells
  notebookAddCell: (nbId, data) => request('POST', `/api/v1/notebook/cell/add/${nbId}`, data),
  notebookDeleteCell: (nbId, cellId) => request('DELETE', `/api/v1/notebook/cell/delete/${nbId}/${cellId}`),
  notebookMoveCell: (nbId, cellId, data) => request('POST', `/api/v1/notebook/cell/move/${nbId}/${cellId}`, data),
  notebookExecuteCell: (nbId, cellId, data) => request('POST', `/api/v1/notebook/cell/execute/${nbId}/${cellId}`, data),
  notebookExecuteAll: (nbId) => request('POST', `/api/v1/notebook/execute-all/${nbId}`),
  notebookDownload: (nbId) => request('GET', `/api/v1/notebook/download/${nbId}`),

  // Notebook — Generate
  notebookGenerate: (data) => request('POST', '/api/v1/notebook/generate', data),

  // Airflow ETL — DAGs
  airflowListDags: () => request('GET', '/api/v1/airflow/dags'),
  airflowCreateDag: (data) => request('POST', '/api/v1/airflow/dags', data),
  airflowCreateEtl: (data) => request('POST', '/api/v1/airflow/dags/create-etl', data),
  airflowGetDag: (id) => request('GET', `/api/v1/airflow/dags/${id}`),
  airflowDeleteDag: (id) => request('DELETE', `/api/v1/airflow/dags/${id}`),

  // Airflow ETL — Tasks
  airflowAddTask: (dagId, data) => request('POST', `/api/v1/airflow/dags/${dagId}/tasks`, data),
  airflowUpdateTask: (dagId, taskId, data) => request('PUT', `/api/v1/airflow/dags/${dagId}/tasks/${taskId}`, data),
  airflowDeleteTask: (dagId, taskId) => request('DELETE', `/api/v1/airflow/dags/${dagId}/tasks/${taskId}`),

  // Airflow ETL — Edges
  airflowAddEdge: (dagId, data) => request('POST', `/api/v1/airflow/dags/${dagId}/edges`, data),
  airflowDeleteEdge: (dagId, edgeId) => request('DELETE', `/api/v1/airflow/dags/${dagId}/edges/${edgeId}`),

  // Airflow ETL — Run
  airflowRunDag: (dagId) => request('POST', `/api/v1/airflow/dags/${dagId}/run`),
  airflowDagRuns: (dagId) => request('GET', `/api/v1/airflow/dags/${dagId}/runs`),

  // Airflow ETL — Export / Deploy
  airflowExportDag: (dagId) => request('GET', `/api/v1/airflow/dags/${dagId}/export`),
  airflowDeployDag: (dagId, data) => request('POST', `/api/v1/airflow/dags/${dagId}/deploy`, data),

  // Airflow ETL — Task templates
  airflowTaskTemplates: () => request('GET', '/api/v1/airflow/task-templates'),
};

export default api;
