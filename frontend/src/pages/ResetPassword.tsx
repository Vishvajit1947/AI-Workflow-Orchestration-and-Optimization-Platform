/**
 * Reset password page, opened from the link in a password reset email (?token=...).
 */
import React, { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import AuthLayout from '../components/AuthLayout';
import {
  AuthHeading, FormAlert, PasswordField, PasswordStrength, SubmitButton, authLinkClass,
} from '../components/auth/AuthFields';
import * as authApi from '../api/authApi';
import { getErrorMessage } from '../lib/errors';

const MIN_PASSWORD_LENGTH = 12;

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  if (!token) {
    return (
      <AuthLayout>
        <AuthHeading title="Invalid reset link" subtitle="This password reset link is invalid or has expired." />
        <Link to="/forgot-password" className={authLinkClass}>Request a new reset link</Link>
      </AuthLayout>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword({ token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeading title="Set a new password" />

      {success && (
        <FormAlert tone="success">
          <p className="font-medium">Password reset.</p>
          <p>Redirecting to sign in…</p>
        </FormAlert>
      )}
      {error && <FormAlert tone="error">{error}</FormAlert>}

      {!success && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <PasswordField
            id="newPassword" label="New password" autoComplete="new-password" required
            value={newPassword} onChange={setNewPassword}
          >
            <p className="mt-1.5 text-xs text-gray-500">At least {MIN_PASSWORD_LENGTH} characters.</p>
            <PasswordStrength password={newPassword} />
          </PasswordField>
          <PasswordField
            id="confirmPassword" label="Confirm password" autoComplete="new-password" required
            value={confirmPassword} onChange={setConfirmPassword}
          />
          <SubmitButton loading={loading}>Reset password</SubmitButton>
        </form>
      )}
    </AuthLayout>
  );
}
