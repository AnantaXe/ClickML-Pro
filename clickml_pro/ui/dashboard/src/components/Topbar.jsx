import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Wifi, WifiOff } from 'lucide-react';
import api from '../api';

const pageTitles = {
  '/': 'Overview',
  '/training': 'Model Training',
  '/quantization': 'Quantization',
  '/registry': 'Model Registry',
  '/data': 'Data Engineering',
  '/governance': 'Governance',
  '/notebook': 'Notebook',
};

export default function Topbar() {
  const { pathname } = useLocation();
  const [online, setOnline] = useState(null);
  const [version, setVersion] = useState('');

  useEffect(() => {
    const check = () => {
      api.health()
        .then((data) => {
          setOnline(true);
          if (data?.version) setVersion(data.version);
        })
        .catch(() => setOnline(false));
    };
    check();
    const iv = setInterval(check, 15000);
    return () => clearInterval(iv);
  }, []);

  return (
    <header className="topbar">
      <span className="topbar-title">{pageTitles[pathname] || 'ClickML Pro'}</span>
      <div className="topbar-right">
        {version && (
          <span style={{ fontSize: '.7rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            {version}
          </span>
        )}
        {online !== null && (
          <span className={`status-badge ${online ? 'online' : 'offline'}`}>
            {online ? <Wifi size={12} /> : <WifiOff size={12} />}
            <span className="status-dot" />
            {online ? 'Connected' : 'Offline'}
          </span>
        )}
      </div>
    </header>
  );
}
