/**
 * Tests for Login and Signup page branding header.
 *
 * Verifies that the branding header (logo, title, tagline) is rendered
 * consistently on both pages, and that the forms render correctly.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { Login } from '../pages/Login';
import { Signup } from '../pages/Signup';

// Mock useAuth to provide a valid context
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    status: 'anon',
    user: null,
    error: null,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Mock authApi module to avoid network calls
vi.mock('../lib/authApi', () => ({
  AuthError: class AuthError extends Error {
    status: number;
    rateLimitScope?: 'ip' | 'global';
    constructor(status: number, message: string, rateLimitScope?: 'ip' | 'global') {
      super(message);
      this.status = status;
      this.rateLimitScope = rateLimitScope;
    }
  },
  login: vi.fn().mockResolvedValue({ id: 'test', email: 'test@test' }),
  signup: vi.fn().mockResolvedValue({ id: 'test', email: 'test@test' }),
  logout: vi.fn().mockResolvedValue(undefined),
  me: vi.fn().mockResolvedValue({
    id: 'test',
    email: 'test@test',
    is_admin: false,
    messages_used_today: 0,
    messages_remaining_today: 25,
    rate_window_resets_at: null,
  }),
}));

const brandingText = "Ask Cole Medin's YouTube library anything";

describe('Login page', () => {
  it('renders branding header with logo, title, and tagline', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByAltText('DynaChat logo')).toBeInTheDocument();
    expect(screen.getByText('DynaChat')).toBeInTheDocument();
    expect(screen.getByText(brandingText)).toBeInTheDocument();
  });

  it('renders the login form with all required fields', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /log in/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /email/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  it('renders a link to the signup page', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /sign up/i })).toHaveAttribute('href', '/signup');
  });
});

describe('Signup page', () => {
  it('renders branding header with logo, title, and tagline', () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    expect(screen.getByAltText('DynaChat logo')).toBeInTheDocument();
    expect(screen.getByText('DynaChat')).toBeInTheDocument();
    expect(screen.getByText(brandingText)).toBeInTheDocument();
  });

  it('renders the signup form with all required fields', () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /email/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
  });

  it('renders a link to the login page', () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /log in/i })).toHaveAttribute('href', '/login');
  });
});

describe('Login and Signup branding consistency', () => {
  it('both pages render identical branding structure', () => {
    const { container: loginContainer } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    const { container: signupContainer } = render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );

    // Both should have the logo img with same alt text
    const loginLogo = loginContainer.querySelector('img[alt="DynaChat logo"]');
    const signupLogo = signupContainer.querySelector('img[alt="DynaChat logo"]');
    expect(loginLogo).toBeInTheDocument();
    expect(signupLogo).toBeInTheDocument();

    // Both should have DynaChat title
    const loginTitle = loginContainer.querySelector('.text-xl.font-semibold');
    const signupTitle = signupContainer.querySelector('.text-xl.font-semibold');
    expect(loginTitle?.textContent).toBe('DynaChat');
    expect(signupTitle?.textContent).toBe('DynaChat');

    // Both should have the tagline
    expect(loginContainer.textContent).toContain(brandingText);
    expect(signupContainer.textContent).toContain(brandingText);
  });
});
