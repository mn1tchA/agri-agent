import { Leaf, Database, Wifi, WifiOff, Loader2, LogOut, MapPin, LayoutDashboard, Sprout, Shield } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { API_BASE } from '../constants';
import { useAuthStore } from '../store/useAuthStore';
import { useFarmStore } from '../store/useFarmStore';

function useBackendPing() {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    const check = async () => {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3000);
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal, cache: 'no-store' });
        setOnline(res.ok);
      } catch {
        setOnline(false);
      } finally {
        clearTimeout(t);
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);
  return online;
}

export function Header() {
  const online = useBackendPing();
  const location = useLocation();
  const navigate = useNavigate();

  const { user, logout } = useAuthStore();
  const { farms, selectedFarm, selectFarm, fetchFarms } = useFarmStore();

  useEffect(() => {
    if (farms.length === 0) {
      fetchFarms();
    }
  }, [farms.length, fetchFarms]);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navLinks = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/analytics', label: 'Analytics', icon: Database },
    { path: '/farms', label: 'Farms', icon: Sprout },
  ];

  return (
    <header className="glass-panel px-5 py-3 mb-6 animate-slide-up flex flex-wrap items-center justify-between gap-4 border border-slate-800">
      {/* ── Logo & Brand ── */}
      <div className="flex items-center gap-3">
        <Link to="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/25 group-hover:shadow-emerald-500/40 transition-shadow">
            <Leaf className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-[var(--font-display)] text-base font-bold leading-tight">
              <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                Agri
              </span>
              <span className="text-white"> Agent</span>
            </h1>
            <p className="text-[10px] text-slate-400 leading-tight">Precision Irrigation</p>
          </div>
        </Link>

        {/* System online indicator */}
        <div className="hidden lg:flex items-center ml-2">
          {online === null ? (
            <span className="chip bg-slate-800 text-slate-400 border border-slate-700 text-[11px]">
              <Loader2 className="w-3 h-3 animate-spin-icon" /> Checking
            </span>
          ) : online ? (
            <span className="chip bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-dot-blink flex-shrink-0" />
              <Wifi className="w-3 h-3" /> Online
            </span>
          ) : (
            <span className="chip bg-red-500/10 text-red-400 border border-red-500/25 text-[11px]">
              <WifiOff className="w-3 h-3" /> Offline
            </span>
          )}
        </div>
      </div>

      {/* ── Route Navigation Tabs ── */}
      <nav className="flex items-center gap-1.5 bg-slate-900/60 p-1 rounded-xl border border-slate-800">
        {navLinks.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path || (path === '/dashboard' && location.pathname === '/');
          return (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm shadow-emerald-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* ── User & Farm Selector Controls ── */}
      <div className="flex items-center gap-3">
        {/* Farm Switcher */}
        {farms.length > 0 && (
          <div className="hidden sm:flex items-center gap-2 bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs">
            <MapPin className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <select
              value={selectedFarm?.id ?? ''}
              onChange={(e) => {
                const found = farms.find((f) => f.id === Number(e.target.value));
                if (found) selectFarm(found);
              }}
              className="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer"
            >
              {farms.map((farm) => (
                <option key={farm.id} value={farm.id} className="bg-slate-900 text-white">
                  {farm.name} ({farm.crop_type})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* User Role Badge */}
        {user && (
          <div className="flex items-center gap-2">
            <div className="hidden md:flex flex-col items-end">
              <span className="text-xs font-semibold text-white leading-none">{user.username}</span>
              <span className="text-[10px] text-emerald-400 uppercase font-medium mt-0.5 flex items-center gap-1">
                <Shield className="w-2.5 h-2.5" />
                {user.role}
              </span>
            </div>

            <button
              onClick={handleLogout}
              className="p-2 rounded-lg bg-slate-800/80 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-slate-700/60 hover:border-rose-500/40 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
