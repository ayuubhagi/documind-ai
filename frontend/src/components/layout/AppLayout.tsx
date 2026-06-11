import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm font-medium transition ${
    isActive ? "bg-slate-800 text-brand-400" : "text-slate-300 hover:bg-slate-800/60"
  }`;

export default function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-8 px-2">
          <span className="font-display text-xl font-bold text-brand-400">DocuMind</span>
          <span className="ml-1 text-xs uppercase tracking-widest text-slate-500">AI</span>
        </div>

        <nav className="flex-1 space-y-1">
          <NavLink to="/dashboard" className={navLinkClass}>
            Documents
          </NavLink>
          <NavLink to="/analytics" className={navLinkClass}>
            Analytics
          </NavLink>
        </nav>

        <div className="border-t border-slate-800 pt-4">
          <p className="truncate px-2 text-sm text-slate-400" title={user?.email}>
            {user?.full_name}
          </p>
          <button
            className="mt-2 w-full rounded-lg px-3 py-2 text-left text-sm text-slate-400 transition hover:bg-slate-800/60 hover:text-slate-200"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
