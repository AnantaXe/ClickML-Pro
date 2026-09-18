import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Brain,
  Layers,
  Database,
  Archive,
  Shield,
  BookOpen,
} from 'lucide-react';

const mainLinks = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/training', label: 'Training', icon: Brain },
  { to: '/quantization', label: 'Quantization', icon: Layers },
  { to: '/registry', label: 'Model Registry', icon: Archive },
];

const dataLinks = [
  { to: '/data', label: 'Data Engineering', icon: Database },
  { to: '/governance', label: 'Governance', icon: Shield },
  { to: '/notebook', label: 'Notebook', icon: BookOpen },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="logo-icon">C</div>
        <div className="brand-text">
          <h1>ClickML Pro</h1>
          <span>Enterprise MLOps</span>
        </div>
      </div>

      <nav className="sidebar-section">
        <div className="section-label">Model Operations</div>
        {mainLinks.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <Icon className="nav-icon" size={17} />
            {label}
          </NavLink>
        ))}

        <div className="section-label" style={{ marginTop: '.5rem' }}>Data & Ops</div>
        {dataLinks.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <Icon className="nav-icon" size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        v0.1.0 -- Apache-2.0
      </div>
    </aside>
  );
}
