'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { register } from '@/lib/api-client';
import { ErrorAlert } from '@/components/ErrorAlert';
import { LoadingSpinner } from '@/components/LoadingSpinner';

export default function RegisterPage() {
  const router = useRouter();
  const auth = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate passwords match
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setLoading(true);

    try {
      const tokens = await register({ email, password, full_name: fullName });
      auth.login(tokens.access_token, tokens.refresh_token);
      router.push('/upload');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-12">
      <div className="max-w-md w-full space-y-8">
        {/* Logo */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-2 mb-2">
            <svg className="w-12 h-12 text-primary" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 18c-4 0-7-3.58-7-8V8.3l7-3.11L19 8.3V12c0 4.42-3 8-7 8z"/>
              <path d="M9 12l2 2 4-4"/>
            </svg>
          </Link>
          <h1 className="text-display text-gray-900">Create your account</h1>
          <p className="mt-2 text-body-sm text-gray-600">
            Already have an account?{' '}
            <Link href="/auth/login" className="font-medium text-primary hover:text-primary-hover">
              Sign in
            </Link>
          </p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-lg shadow-md p-8">
          {error && (
            <div className="mb-6">
              <ErrorAlert message={error} onRetry={() => setError(null)} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="fullName" className="block text-body-sm font-medium text-gray-900 mb-2">
                Full name
              </label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="
                  w-full px-4 py-3 text-body
                  border border-gray-300 rounded-md
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                  disabled:bg-gray-50 disabled:text-gray-400
                "
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-body-sm font-medium text-gray-900 mb-2">
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="
                  w-full px-4 py-3 text-body
                  border border-gray-300 rounded-md
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                  disabled:bg-gray-50 disabled:text-gray-400
                "
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-body-sm font-medium text-gray-900 mb-2">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="
                  w-full px-4 py-3 text-body
                  border border-gray-300 rounded-md
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                  disabled:bg-gray-50 disabled:text-gray-400
                "
                disabled={loading}
              />
              <p className="mt-1 text-caption text-gray-500">
                Must be at least 8 characters
              </p>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-body-sm font-medium text-gray-900 mb-2">
                Confirm password
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="
                  w-full px-4 py-3 text-body
                  border border-gray-300 rounded-md
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent
                  disabled:bg-gray-50 disabled:text-gray-400
                "
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="
                w-full flex justify-center items-center gap-2
                px-6 py-3 text-body font-medium text-white
                bg-primary rounded-md
                hover:bg-primary-hover
                focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary
                disabled:bg-gray-300 disabled:cursor-not-allowed
                transition-colors
              "
            >
              {loading ? (
                <>
                  <LoadingSpinner size="sm" />
                  <span>Creating account...</span>
                </>
              ) : (
                'Create account'
              )}
            </button>
          </form>
        </div>

        {/* Footer note */}
        <p className="text-center text-caption text-gray-500">
          By creating an account, you agree to our{' '}
          <Link href="/terms" className="text-primary hover:text-primary-hover">
            Terms of Service
          </Link>{' '}
          and{' '}
          <Link href="/privacy" className="text-primary hover:text-primary-hover">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
