/**
 * Authentication types matching backend schemas.
 */

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_email_verified: boolean;
  is_active: boolean;
  role: string;
  created_at: string;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  terms_accepted: boolean;
}

export interface LoginData {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface ForgotPasswordData {
  email: string;
}

export interface ResetPasswordData {
  token: string;
  new_password: string;
}

export interface AuthResponse {
  message?: string;
  user?: User;
}

// Kept here so existing auth imports keep working; the implementation is shared app-wide.
export { getErrorMessage } from '../lib/errors';
