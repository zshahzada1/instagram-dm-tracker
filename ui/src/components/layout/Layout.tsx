import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="min-h-screen bg-ig-background text-ig-text">
      <Sidebar />
      <main className="ml-[260px] min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
