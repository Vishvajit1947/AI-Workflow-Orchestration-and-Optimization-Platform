/**
 * Form building blocks shared by the login, sign-up and password pages.
 */
import React, { useState } from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

const INPUT =
  'w-full rounded-lg border border-gray-300 px-4 py-2.5 text-gray-900 placeholder:text-gray-400 ' +
  'focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500';

const LABEL = 'mb-1.5 block text-sm font-medium text-gray-700';

interface FieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}

export const TextField: React.FC<FieldProps> = ({ id, label, onChange, ...input }) => (
  <div>
    <label htmlFor={id} className={LABEL}>{label}</label>
    <input id={id} className={INPUT} onChange={(e) => onChange(e.target.value)} {...input} />
  </div>
);

export const PasswordField: React.FC<Omit<FieldProps, 'type'> & { children?: React.ReactNode }> = ({
  id, label, onChange, children, ...input
}) => {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className={LABEL}>{label}</label>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          className={`${INPUT} pr-12`}
          onChange={(e) => onChange(e.target.value)}
          {...input}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded text-gray-500 hover:text-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
        >
          {visible ? <EyeOff size={20} /> : <Eye size={20} />}
        </button>
      </div>
      {children}
    </div>
  );
};

const STRENGTH = [
  { label: '', color: '' },
  { label: 'Weak', color: 'bg-red-500' },
  { label: 'Fair', color: 'bg-yellow-500' },
  { label: 'Good', color: 'bg-blue-500' },
  { label: 'Strong', color: 'bg-green-500' },
];

const passwordStrength = (pwd: string): number => {
  let score = 0;
  if (pwd.length >= 8) score++;
  if (pwd.length >= 12) score++;
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
  if (/\d/.test(pwd)) score++;
  if (/[^a-zA-Z\d]/.test(pwd)) score++;
  return Math.min(score, 4);
};

/** Four-segment strength meter shown under a new-password field. */
export const PasswordStrength: React.FC<{ password: string }> = ({ password }) => {
  if (!password) return null;
  const score = passwordStrength(password);
  return (
    <div className="mt-2">
      <div className="mb-1 flex gap-1" aria-hidden>
        {[1, 2, 3, 4].map((level) => (
          <div key={level} className={`h-1 flex-1 rounded ${level <= score ? STRENGTH[score].color : 'bg-gray-200'}`} />
        ))}
      </div>
      <p className="text-xs text-gray-600">Password strength: {STRENGTH[score].label || 'Too weak'}</p>
    </div>
  );
};

export const FormAlert: React.FC<{ tone: 'error' | 'success'; children: React.ReactNode }> = ({ tone, children }) => (
  <div
    role={tone === 'error' ? 'alert' : 'status'}
    className={`mb-6 rounded-lg border p-4 text-sm ${
      tone === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'
    }`}
  >
    {children}
  </div>
);

export const SubmitButton: React.FC<{ loading: boolean; children: React.ReactNode }> = ({ loading, children }) => (
  <button
    type="submit"
    disabled={loading}
    className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
  >
    {loading && <Loader2 size={18} className="animate-spin" />}
    {children}
  </button>
);

export const AuthHeading: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => (
  <div className="mb-8">
    <h1 className="text-2xl font-semibold tracking-tight text-gray-900">{title}</h1>
    {subtitle && <p className="mt-1.5 text-gray-600">{subtitle}</p>}
  </div>
);

export const authLinkClass = 'font-medium text-primary-600 hover:text-primary-500';
