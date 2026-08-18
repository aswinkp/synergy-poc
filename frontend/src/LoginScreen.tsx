import { useState } from 'react'
import { ArrowRight, BarChart3, Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { api } from './api'
import type { AuthUser } from './types'

interface LoginScreenProps {
  onAuthenticated: (user: AuthUser) => void
}

export default function LoginScreen({ onAuthenticated }: LoginScreenProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!email.trim() || !password || loading) return
    setLoading(true)
    setError('')
    try {
      onAuthenticated(await api.login(email.trim(), password))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not sign in')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-brand">
        <div className="brand-mark"><BarChart3 size={19} /></div>
        <div><strong>Synergy</strong><span>Learning intelligence</span></div>
      </div>

      <section className="login-card" aria-labelledby="login-title">
        <div className="login-icon"><LockKeyhole size={22} /></div>
        <p className="eyebrow">Secure workspace</p>
        <h1 id="login-title">Welcome back</h1>
        <p className="login-copy">Sign in to explore your organization’s learning and workforce data.</p>

        <form onSubmit={submit}>
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
            autoFocus
          />

          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
            <button type="button" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>

          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit" disabled={!email.trim() || !password || loading}>
            <span>{loading ? 'Signing in…' : 'Sign in'}</span><ArrowRight size={17} />
          </button>
        </form>

        <p className="provisioning-note">Accounts are provisioned by your administrator. There is no public signup.</p>
      </section>
    </main>
  )
}
