import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole, LoginRequest } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<User>;
  logout: () => void;
  hasRole: (allowedRoles: UserRole[]) => boolean;
  canExecuteRecovery: boolean;
  canManageUsers: boolean;
  canManageGuardrails: boolean;
  isReadOnly: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('payrecover_token'));
  const [user, setUser] = useState<User | null>(() => {
    const cached = localStorage.getItem('payrecover_user');
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Validate existing token on mount
  useEffect(() => {
    const verifySession = async () => {
      if (token) {
        try {
          const profile = await api.getMe();
          setUser(profile);
          localStorage.setItem('payrecover_user', JSON.stringify(profile));
        } catch (err) {
          console.warn('Session expired or invalid, logging out.');
          localStorage.removeItem('payrecover_token');
          localStorage.removeItem('payrecover_user');
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    verifySession();
  }, [token]);

  const login = useCallback(async (credentials: LoginRequest): Promise<User> => {
    const res = await api.login(credentials.email, credentials.password);
    setToken(res.access_token);
    setUser(res.user);
    localStorage.setItem('payrecover_token', res.access_token);
    localStorage.setItem('payrecover_user', JSON.stringify(res.user));
    return res.user;
  }, []);

  const logout = useCallback(() => {
    if (token) {
      api.logout().catch(() => {});
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem('payrecover_token');
    localStorage.removeItem('payrecover_user');
  }, [token]);

  const hasRole = useCallback((allowedRoles: UserRole[]): boolean => {
    if (!user) return false;
    return allowedRoles.includes(user.role);
  }, [user]);

  const canExecuteRecovery = user ? ['ADMIN', 'OPERATOR'].includes(user.role) : false;
  const canManageUsers = user ? user.role === 'ADMIN' : false;
  const canManageGuardrails = user ? user.role === 'ADMIN' : false;
  const isReadOnly = user ? ['ANALYST', 'VIEWER'].includes(user.role) : true;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        hasRole,
        canExecuteRecovery,
        canManageUsers,
        canManageGuardrails,
        isReadOnly
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
