'use client'

import { login, signup, signInWithGoogle } from './actions'
import { useState } from 'react'
import { Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleGoogleLogin = async () => {
    setError(null)
    setLoading(true)
    try {
      await signInWithGoogle()
    } catch (e: any) {
      if (e?.message !== 'NEXT_REDIRECT') {
        setError(e.message || 'Google 로그인을 시작하지 못했습니다.')
        setLoading(false)
      }
    }
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    setLoading(true)

    const formData = new FormData(event.currentTarget)
    const action = (event.nativeEvent as any).submitter.value

    try {
      const result = action === 'login' ? await login(formData) : await signup(formData)
      if (result && 'error' in result && result.error) setError(result.error)
      if (result && 'message' in result) setMessage(result.message)
    } catch {
      setError('처리 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen py-6">
      <div className="mobile-shell">
        <div className="surface p-5">
          <p className="text-xs font-semibold text-primary">Thunder Navigator</p>
          <h1 className="mt-2 text-xl font-bold">학습 내비게이션 시작하기</h1>
          <p className="mt-1 text-sm text-muted-foreground">로그인 후 과목을 만들고 오디오+교재 분석을 시작하세요.</p>

          <form onSubmit={handleSubmit} className="mt-5 space-y-3">
            <label className="block text-sm font-medium">
              이메일
              <input
                className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2.5 text-sm"
                id="email"
                name="email"
                type="email"
                placeholder="student@example.com"
                required
              />
            </label>

            <label className="block text-sm font-medium">
              비밀번호
              <input
                className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2.5 text-sm"
                id="password"
                name="password"
                type="password"
                required
              />
            </label>

            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>}
            {message && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-600">{message}</p>}

            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                className="inline-flex items-center justify-center rounded-xl bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
                type="submit"
                name="action"
                value="login"
                disabled={loading}
              >
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                로그인
              </button>
              <button
                className="rounded-xl border border-border bg-card px-3 py-2.5 text-sm font-semibold disabled:opacity-60"
                type="submit"
                name="action"
                value="signup"
                disabled={loading}
              >
                회원가입
              </button>
            </div>
          </form>

          <button
            type="button"
            className="mt-3 w-full rounded-xl border border-border bg-card px-3 py-2.5 text-sm font-semibold disabled:opacity-60"
            onClick={handleGoogleLogin}
            disabled={loading}
          >
            Google로 계속하기
          </button>
        </div>
      </div>
    </main>
  )
}
