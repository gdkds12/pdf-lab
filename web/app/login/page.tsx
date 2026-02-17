'use client'

import { login, signup, signInWithGoogle } from './actions'
import { useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { GrainOverlay } from '@/components/grain-overlay'

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
    <main className="relative min-h-screen overflow-hidden bg-background">
      <GrainOverlay />
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-[#1275d8]/30 blur-3xl" />
        <div className="absolute -right-20 bottom-0 h-80 w-80 rounded-full bg-[#e19136]/20 blur-3xl" />
      </div>

      <div className="th-shell flex min-h-screen items-center justify-center">
        <div className="th-card w-full max-w-md">
          <div className="mb-6 flex items-center justify-between">
            <p className="th-pill inline-flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5" />
              썬더 네비게이터
            </p>
            <Link href="/" className="text-xs text-foreground/70 transition hover:text-foreground">
              홈으로
            </Link>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">학습 내비게이션 시작하기</h1>
          <p className="mt-2 text-sm text-foreground/70">로그인 후 과목을 만들고 오디오/교재 분석을 시작하세요.</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-3">
            <label className="block text-sm font-medium text-foreground/90">
              이메일
              <input
                className="mt-1 w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-sm placeholder:text-foreground/40 focus:border-primary focus:outline-none"
                id="email"
                name="email"
                type="email"
                placeholder="student@example.com"
                required
              />
            </label>

            <label className="block text-sm font-medium text-foreground/90">
              비밀번호
              <input
                className="mt-1 w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-sm placeholder:text-foreground/40 focus:border-primary focus:outline-none"
                id="password"
                name="password"
                type="password"
                required
              />
            </label>

            {error && <p className="rounded-xl border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</p>}
            {message && <p className="rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{message}</p>}

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
                className="rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-sm font-semibold text-foreground disabled:opacity-60"
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
            className="mt-3 w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-sm font-semibold text-foreground transition hover:bg-white/10 disabled:opacity-60"
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
