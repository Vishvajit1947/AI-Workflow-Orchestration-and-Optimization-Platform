/**
 * Form building blocks shared by the login, sign-up and password pages.
 */
import React, { useState } from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { Notice } from '../ui/States';

const INPUT = 'input h-[46px] px-4 text-[15px]';

interface FieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}

export const TextField: React.FC<FieldProps> = ({ id, label, onChange, ...input }) => (
  <div>
    <label htmlFor={id} className="label">{label}</label>
    <input id={id} className={INPUT} onChange={(e) => onChange(e.target.value)} {...input} />
  </div>
);

export const PasswordField: React.FC<Omit<FieldProps, 'type'> & { children?: React.ReactNode }> = ({
  id, label, onChange, children, ...input
}) => {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
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
          className="btn btn-ghost btn-icon btn-sm absolute right-2 top-1/2 -translate-y-1/2"
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
        >
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
      {children}
    </div>
  );
};

const STRENGTH = [
  { label: '', color: '' },
  { label: 'Weak', color: 'bg-danger' },
  { label: 'Fair', color: 'bg-[#d08a1c]' },
  { label: 'Good', color: 'bg-periwinkle' },
  { label: 'Strong', color: 'bg-primary' },
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
    <div className="mt-2.5">
      <div className="mb-1.5 flex gap-1" aria-hidden>
        {[1, 2, 3, 4].map((level) => (
          <div key={level} className={`h-1 flex-1 rounded-full ${level <= score ? STRENGTH[score].color : 'bg-lavender'}`} />
        ))}
      </div>
      <p className="text-xs text-ink-muted">Password strength: {STRENGTH[score].label || 'Too weak'}</p>
    </div>
  );
};

export const FormAlert: React.FC<{ tone: 'error' | 'success'; children: React.ReactNode }> = ({ tone, children }) => (
  <Notice tone={tone === 'error' ? 'danger' : 'success'} className="mb-6">{children}</Notice>
);

export const SubmitButton: React.FC<{ loading: boolean; children: React.ReactNode }> = ({ loading, children }) => (
  <button type="submit" disabled={loading} className="btn btn-primary h-[46px] w-full text-[15px]">
    {loading && <Loader2 size={17} className="animate-spin" />}
    {children}
  </button>
);

export const AuthHeading: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => (
  <div className="mb-8">
    <h1 className="text-heading-2 font-medium text-ink">{title}</h1>
    {subtitle && <p className="mt-2 text-[15px] font-light text-ink-secondary">{subtitle}</p>}
  </div>
);

export const authLinkClass = 'link';

/** Checkbox row used for "remember me" and terms. */
export const CheckboxField: React.FC<{
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
}> = ({ checked, onChange, children }) => (
  <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-secondary">
    <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="checkbox mt-0.5" />
    <span>{children}</span>
  </label>
);
