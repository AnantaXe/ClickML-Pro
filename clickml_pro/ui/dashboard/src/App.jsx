import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Training from './pages/Training';
import Quantization from './pages/Quantization';
import Registry from './pages/Registry';
import DataEngineering from './pages/DataEngineering';
import Governance from './pages/Governance';
import Notebook from './pages/Notebook';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/training" element={<Training />} />
        <Route path="/quantization" element={<Quantization />} />
        <Route path="/registry" element={<Registry />} />
        <Route path="/data" element={<DataEngineering />} />
        <Route path="/governance" element={<Governance />} />
        <Route path="/notebook" element={<Notebook />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
