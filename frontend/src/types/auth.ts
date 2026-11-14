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

export interface VerifyEmailData {
  token: string;
}

export interface AuthResponse {
  message?: string;
  user?: User;
}

/**
 * API error response structure.
 */
export interface ApiError {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
    status?: number;
  };
  message?: string;
}

/**
 * Type guard to check if an error is an ApiError.
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    ('response' in error || 'message' in error)
  );
}

/**
 * Extract error message from unknown error object.
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.response?.data?.detail || 
           error.response?.data?.message || 
           error.message || 
           'An unexpected error occurred';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}
