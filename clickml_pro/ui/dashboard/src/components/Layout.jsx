import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { ToastProvider } from './Toast';

export default function Layout() {
  return (
    <ToastProvider>
      <Sidebar />
      <div className="main-area">
        <Topbar />
        <div className="content">
          <Outlet />
        </div>
      </div>
    </ToastProvider>
  );
}
