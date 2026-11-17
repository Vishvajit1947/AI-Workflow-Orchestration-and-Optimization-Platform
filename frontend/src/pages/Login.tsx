/**
 * Login page.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from '../components/AuthLayout';
import {
  AuthHeading, FormAlert, PasswordField, SubmitButton, TextField, authLinkClass,
} from '../components/auth/AuthFields';
import { useAuth } from '../hooks/useAuth';
import { getErrorMessage } from '../lib/errors';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login({ email, password, remember_me: rememberMe });
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeading title="Welcome back" subtitle="Sign in to continue to AI Orchestrator" />

      {error && <FormAlert tone="error">{error}</FormAlert>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <TextField
          id="email" label="Email" type="email" autoComplete="email" required
          value={email} onChange={setEmail} placeholder="you@example.com"
        />
        <PasswordField
          id="password" label="Password" autoComplete="current-password" required
          value={password} onChange={setPassword}
        />

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Remember me
          </label>
          <Link to="/forgot-password" className={`text-sm ${authLinkClass}`}>
            Forgot password?
          </Link>
        </div>

        <SubmitButton loading={loading}>Sign in</SubmitButton>
      </form>

      <p className="mt-8 text-center text-sm text-gray-600">
        Don't have an account?{' '}
        <Link to="/signup" className={authLinkClass}>Create one</Link>
      </p>
    </AuthLayout>
  );
}
