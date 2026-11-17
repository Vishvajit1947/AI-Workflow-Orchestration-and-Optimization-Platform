/**
 * Sign-up page. A successful registration signs the user in.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from '../components/AuthLayout';
import {
  AuthHeading, FormAlert, PasswordField, PasswordStrength, SubmitButton, TextField, authLinkClass,
} from '../components/auth/AuthFields';
import { useAuth } from '../hooks/useAuth';
import { getErrorMessage } from '../lib/errors';

const MIN_PASSWORD_LENGTH = 12;

export default function Signup() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { register } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
      return;
    }
    if (!termsAccepted) {
      setError('You must accept the terms of service and privacy policy');
      return;
    }

    setLoading(true);
    try {
      await register({ email, password, full_name: fullName, terms_accepted: termsAccepted });
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeading title="Create your account" subtitle="Start planning and running AI workflows" />

      {error && <FormAlert tone="error">{error}</FormAlert>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <TextField
          id="fullName" label="Full name" autoComplete="name" required
          value={fullName} onChange={setFullName}
        />
        <TextField
          id="email" label="Email" type="email" autoComplete="email" required
          value={email} onChange={setEmail} placeholder="you@example.com"
        />
        <PasswordField
          id="password" label="Password" autoComplete="new-password" required
          value={password} onChange={setPassword} aria-describedby="password-hint"
        >
          <p id="password-hint" className="mt-1.5 text-xs text-gray-500">At least {MIN_PASSWORD_LENGTH} characters.</p>
          <PasswordStrength password={password} />
        </PasswordField>
        <PasswordField
          id="confirmPassword" label="Confirm password" autoComplete="new-password" required
          value={confirmPassword} onChange={setConfirmPassword}
        />

        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          I agree to the terms of service and privacy policy
        </label>

        <SubmitButton loading={loading}>Create account</SubmitButton>
      </form>

      <p className="mt-8 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <Link to="/login" className={authLinkClass}>Sign in</Link>
      </p>
    </AuthLayout>
  );
}
