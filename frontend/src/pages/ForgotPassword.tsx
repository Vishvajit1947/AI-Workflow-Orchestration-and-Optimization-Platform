/**
 * Forgot password page: requests a reset link for an email address.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import AuthLayout from '../components/AuthLayout';
import { AuthHeading, FormAlert, SubmitButton, TextField, authLinkClass } from '../components/auth/AuthFields';
import * as authApi from '../api/authApi';
import { getErrorMessage } from '../lib/errors';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.forgotPassword({ email });
      setSuccess(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeading title="Reset your password" subtitle="Enter your account email to request a password reset link." />

      {success && (
        <FormAlert tone="success">
          If an account exists for this email address, password reset instructions have been sent.
        </FormAlert>
      )}
      {error && <FormAlert tone="error">{error}</FormAlert>}

      {!success && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <TextField
            id="email" label="Email" type="email" autoComplete="email" required
            value={email} onChange={setEmail} placeholder="you@example.com"
          />
          <SubmitButton loading={loading}>Send reset link</SubmitButton>
        </form>
      )}

      <Link to="/login" className={`mt-8 flex items-center justify-center gap-2 text-sm ${authLinkClass}`}>
        <ArrowLeft size={16} aria-hidden />
        Back to sign in
      </Link>
    </AuthLayout>
  );
}
