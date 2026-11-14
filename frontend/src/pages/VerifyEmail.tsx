/**
 * Email verification page.
 */

import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2, Mail } from 'lucide-react';
import AuthLayout from '../components/AuthLayout';
import * as authApi from '../api/authApi';
import { getErrorMessage } from '../types/auth';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'idle'>(
    token ? 'loading' : 'idle'
  );
  const [message, setMessage] = useState('');
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (token) {
      verifyToken(token);
    } else if (location.state?.message) {
      setMessage(location.state.message);
    }
  }, [token]);

  const verifyToken = async (token: string) => {
    try {
      const result = await authApi.verifyEmail({ token });
      setStatus('success');
      setMessage(result.message);
    } catch (err: unknown) {
      setStatus('error');
      setMessage(getErrorMessage(err));
    }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      const result = await authApi.resendVerification();
      setMessage(result.message);
      setStatus('idle');
    } catch (err: unknown) {
      setMessage(getErrorMessage(err));
    } finally {
      setResending(false);
    }
  };

  return (
    <AuthLayout>
      <div className="text-center">
        {status === 'loading' && (
          <>
            <Loader2 className="w-16 h-16 text-primary-500 animate-spin mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Verifying your email...
            </h1>
            <p className="text-gray-600">Please wait while we verify your email address.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Email verified!</h1>
            <p className="text-gray-600 mb-8">{message}</p>
            <button
              onClick={() => navigate('/login')}
              className="px-6 py-3 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-600"
            >
              Go to Dashboard
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Verification failed</h1>
            <p className="text-gray-600 mb-8">{message}</p>
            <button
              onClick={handleResend}
              disabled={resending}
              className="px-6 py-3 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
            >
              {resending && <Loader2 size={20} className="animate-spin" />}
              Resend verification email
            </button>
          </>
        )}

        {status === 'idle' && (
          <>
            <Mail className="w-16 h-16 text-primary-500 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Check your email</h1>
            <p className="text-gray-600 mb-8">
              {message || 'We sent a verification link to your email address. Click the link in the email to verify your account.'}
            </p>
            <p className="text-sm text-gray-500 mb-4">
              Didn't receive the email? Check your spam folder or request a new one.
            </p>
            <button
              onClick={handleResend}
              disabled={resending}
              className="px-6 py-3 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
            >
              {resending && <Loader2 size={20} className="animate-spin" />}
              Resend verification email
            </button>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
