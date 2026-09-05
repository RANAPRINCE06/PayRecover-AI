import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  Edit2,
  Check,
  X
} from 'lucide-react';
import { User, UserRole, UserCreatePayload } from '../types';
import { api } from '../services/api';
import { useToast } from './Toast';

const ROLE_BADGES: Record<UserRole, { label: string; color: string }> = {
  ADMIN: { label: 'ADMIN', color: 'border-brand-cyan/40 bg-brand-cyan/10 text-brand-cyan' },
  OPERATOR: { label: 'OPERATOR', color: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400' },
  ANALYST: { label: 'ANALYST', color: 'border-brand-indigo/40 bg-brand-indigo/10 text-indigo-300' },
  VIEWER: { label: 'VIEWER', color: 'border-slate-600 bg-dark-700 text-slate-400' }
};

export const AdminUserManagement: React.FC = () => {
  const { showSuccess, showError } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Form State
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<UserRole>('OPERATOR');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchUsers = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      const data = await api.getUsers();
      setUsers(data);
    } catch (err: any) {
      showError('Failed to fetch users', err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showError]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !name.trim() || !password.trim()) {
      showError('Validation Error', 'All fields are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: UserCreatePayload = {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        role,
        password: password.trim()
      };
      const created = await api.createUser(payload);
      showSuccess('User Created', `Added ${created.name} as ${created.role}`);
      setIsCreateModalOpen(false);
      setEmail('');
      setName('');
      setPassword('');
      setRole('OPERATOR');
      fetchUsers(true);
    } catch (err: any) {
      showError('User Creation Failed', err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      const updated = await api.toggleUserActive(user.id);
      showSuccess('Status Updated', `${updated.name} is now ${updated.is_active ? 'Active' : 'Deactivated'}`);
      fetchUsers(true);
    } catch (err: any) {
      showError('Action Denied', err.message);
    }
  };

  const handleChangeRole = async (userId: string, newRole: UserRole) => {
    try {
      const updated = await api.updateUser(userId, { role: newRole });
      showSuccess('Role Updated', `${updated.name} role changed to ${updated.role}`);
      fetchUsers(true);
    } catch (err: any) {
      showError('Update Failed', err.message);
    }
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="w-4 h-4 text-brand-cyan" />
            Merchant Team & RBAC Management
          </h3>
          <p className="text-xs text-slate-400">
            Control access roles (Admin, Operator, Analyst, Viewer) and activate or suspend team members.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchUsers(true)}
            disabled={refreshing || loading}
            className="p-2 bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-300 rounded-lg transition"
            title="Refresh Users"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-brand-cyan' : ''}`} />
          </button>

          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-3 py-1.5 bg-brand-cyan text-dark-900 font-bold text-xs rounded-lg shadow-glow-cyan hover:opacity-90 transition flex items-center gap-1.5"
          >
            <UserPlus className="w-3.5 h-3.5" />
            Add Team Member
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="rounded-2xl bg-dark-850 border border-dark-700 overflow-hidden shadow-xl">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-brand-cyan" />
            <span className="text-xs text-slate-400">Loading user records...</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-800 text-slate-400 border-b border-dark-700 font-mono">
                <tr>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {users.map((u) => {
                  const badge = ROLE_BADGES[u.role] || ROLE_BADGES.VIEWER;
                  return (
                    <tr key={u.id} className="hover:bg-dark-800/60 transition">
                      <td className="py-3 px-4">
                        <div>
                          <div className="font-bold text-white flex items-center gap-1.5">
                            {u.name}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono">{u.email}</div>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <select
                          value={u.role}
                          onChange={(e) => handleChangeRole(u.id, e.target.value as UserRole)}
                          className={`px-2 py-1 rounded text-[10px] font-mono font-bold border ${badge.color} bg-dark-900 focus:outline-none cursor-pointer`}
                        >
                          <option value="ADMIN">ADMIN</option>
                          <option value="OPERATOR">OPERATOR</option>
                          <option value="ANALYST">ANALYST</option>
                          <option value="VIEWER">VIEWER</option>
                        </select>
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                            u.is_active
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                              : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                          }`}
                        >
                          {u.is_active ? (
                            <>
                              <CheckCircle2 className="w-3 h-3" />
                              Active
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3" />
                              Suspended
                            </>
                          )}
                        </span>
                      </td>

                      <td className="py-3 px-4 font-mono text-slate-400 text-[11px]">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleToggleActive(u)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                            u.is_active
                              ? 'border-rose-500/40 text-rose-400 hover:bg-rose-500/10'
                              : 'border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10'
                          }`}
                        >
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="max-w-md w-full p-6 rounded-2xl bg-dark-850 border border-dark-700 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-brand-cyan" />
                Add Merchant Team Member
              </h3>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="text-slate-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Alex Morgan"
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Assign Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-brand-cyan"
                >
                  <option value="ADMIN">ADMIN — Full system access & approvals</option>
                  <option value="OPERATOR">OPERATOR — Recovery tool execution</option>
                  <option value="ANALYST">ANALYST — Analytics & telemetry read-only</option>
                  <option value="VIEWER">VIEWER — Dashboard read-only</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Initial Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 6 characters"
                  className="w-full bg-dark-800 border border-dark-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-brand-cyan"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-slate-300 hover:text-white font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-brand-cyan text-dark-900 font-bold shadow-glow-cyan hover:opacity-90 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Create Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
