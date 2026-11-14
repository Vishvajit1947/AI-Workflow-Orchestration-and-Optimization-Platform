/**
 * Authentication API client.
 */

import api from '../lib/api';
import {
  RegisterData,
  LoginData,
  ForgotPasswordData,
  ResetPasswordData,
  VerifyEmailData,
  User,
  AuthResponse,
} from '../types/auth';

export const register = async (data: RegisterData): Promise<AuthResponse> => {
  const response = await api.post<AuthResponse>('/auth/register', data);
  return response.data;
};

export const login = async (data: LoginData): Promise<User> => {
  const response = await api.post<User>('/auth/login', data);
  return response.data;
};

export const logout = async (): Promise<void> => {
  await api.post('/auth/logout');
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};

export const forgotPassword = async (
  data: ForgotPasswordData
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    '/auth/forgot-password',
    data
  );
  return response.data;
};

export const resetPassword = async (
  data: ResetPasswordData
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    '/auth/reset-password',
    data
  );
  return response.data;
};

export const verifyEmail = async (
  data: VerifyEmailData
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    '/auth/verify-email',
    data
  );
  return response.data;
};

export const resendVerification = async (): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    '/auth/resend-verification'
  );
  return response.data;
};
