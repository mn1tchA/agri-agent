import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Leaf, Lock, User, Eye, EyeOff, ShieldCheck, Activity, Sparkles, AlertCircle } from 'lucide-react';
import { toast } from 'react-toastify';
import { useAuthStore } from '../store/useAuthStore';

export function LoginPage() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('changeme');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, error } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      toast.error('Please enter both username and password.');
      return;
    }

    setIsSubmitting(true);
    const success = await login(username, password);
    setIsSubmitting(false);

    if (success) {
      toast.success(`Welcome back, ${username}!`);
      navigate('/dashboard', { replace: true });
    } else {
      toast.error(error || 'Invalid login credentials.');
    }
  };

  const handleQuickLogin = async (user: string, pass: string) => {
    setUsername(user);
    setPassword(pass);
    setIsSubmitting(true);
    const success = await login(user, pass);
    setIsSubmitting(false);
    if (success) {
      toast.success(`Authenticated as ${user}`);
      navigate('/dashboard', { replace: true });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
      {/* Background radial gradient blobs */}
      <div className="absolute top-1/4 -left-20 w-96 h-96 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-20 w-96 h-96 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />

      <div className="w-full max-w-md relative z-10 animate-fade-in">
        {/* Logo and Brand */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center mx-auto mb-4 shadow-xl shadow-emerald-500/25 animate-float">
            <Leaf className="w-8 h-8 text-white" strokeWidth={2.2} />
          </div>
          <h1 className="text-3xl font-bold font-[var(--font-display)] text-white tracking-tight">
            Agri-Agent Swarm
          </h1>
          <p className="text-slate-400 text-sm mt-1.5">
            Autonomous Multi-Agent Precision Agriculture
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-panel p-8 backdrop-blur-xl border border-slate-700/60 shadow-2xl relative">
          <div className="flex items-center justify-between pb-6 mb-6 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-semibold text-white">Sign In</h2>
              <p className="text-xs text-slate-400">Access farm telemetry and actuation controls</p>
            </div>
            <span className="badge badge-green flex items-center gap-1.5 text-xs py-1 px-2.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              v2.2 Secure
            </span>
          </div>

          {error && (
            <div className="mb-6 p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center gap-3 text-rose-300 text-xs animate-shake">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin or viewer"
                  className="input-field pl-10 text-sm"
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-field pl-10 pr-10 text-sm"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full py-3 justify-center text-sm font-semibold shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating...
                </>
              ) : (
                <>
                  <Activity className="w-4 h-4" />
                  Sign In to Dashboard
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credentials */}
          <div className="mt-8 pt-6 border-t border-slate-800/80">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-3 font-medium">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Quick 1-Click Demo Profiles:</span>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => handleQuickLogin('admin', 'changeme')}
                className="p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-emerald-500/40 text-left transition-all group"
              >
                <div className="text-xs font-semibold text-emerald-400 group-hover:text-emerald-300">
                  Operator (Admin)
                </div>
                <div className="text-[10px] text-slate-300 font-mono mt-0.5">admin / changeme</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Full Actuation & Runs</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('viewer', 'viewer123')}
                className="p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-blue-500/40 text-left transition-all group"
              >
                <div className="text-xs font-semibold text-cyan-400 group-hover:text-cyan-300">
                  Viewer
                </div>
                <div className="text-[10px] text-slate-300 font-mono mt-0.5">viewer / viewer123</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Read-Only Analytics</div>
              </button>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <p className="text-center text-xs text-slate-400 mt-6">
          Agri-Agent Precision Irrigation &bull; Oran Pilot &bull; JWT RBAC Active
        </p>
      </div>
    </div>
  );
}
