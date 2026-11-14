/**
 * Authentication context provider.
 */

import React, { createContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import * as authApi from '../api/authApi';
import { User, LoginData, RegisterData, getErrorMessage } from '../types/auth';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Restore session on mount
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const currentUser = await authApi.getCurrentUser();
        setUser(currentUser);
      } catch (error) {
        // No valid session
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    restoreSession();
  }, []);

  const login = async (data: LoginData) => {
    try {
      const user = await authApi.login(data);
      setUser(user);
      navigate('/');
    } catch (error: unknown) {
      const message = getErrorMessage(error);
      alert(message);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      navigate('/login');
    }
  };

  const register = async (data: RegisterData) => {
    try {
      await authApi.register(data);
      // Do not set user state - user must verify email first
      navigate('/verify-email', {
        state: { message: 'Please check your email to verify your account' },
      });
    } catch (error: unknown) {
      const message = getErrorMessage(error);
      alert(message);
      throw error;
    }
  };

  const isAuthenticated = user !== null;

  return (
    <AuthContext.Provider
      value={{ user, loading, isAuthenticated, login, logout, register }}
    >
      {children}
    </AuthContext.Provider>
  );
}
