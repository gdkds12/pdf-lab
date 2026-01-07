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
       // redirect usually throws an error in Next.js which is expected, 
       // but if it's a real error:
       if (e?.message !== 'NEXT_REDIRECT') {
          setError(e.message || "Failed to initiate Google login")
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
        let result;
        if (action === 'login') {
            result = await login(formData)
        } else {
            result = await signup(formData)
        }
        
        if (result && 'error' in result && result.error) {
            setError(result.error)
        } else if (result && 'message' in result) {
            setMessage(result.message)
        }
    } catch (e) {
        setError("An unexpected error occurred.")
    } finally {
        setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-900/5">
        <div>
          <h2 className="mt-6 text-center text-3xl font-bold tracking-tight text-gray-900">
            PDF-Lab
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Sign in to start your exam preparation
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="-space-y-px rounded-md shadow-sm">
            <div>
              <label htmlFor="email-address" className="sr-only">
                Email address
              </label>
              <input
                id="email-address"
                name="email"
                type="email"
                required
                className="relative block w-full rounded-t-md border-0 py-1.5 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 pl-2"
                placeholder="Email address"
              />
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="relative block w-full rounded-b-md border-0 py-1.5 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 pl-2"
                placeholder="Password"
              />
            </div>
          </div>

          {error && <div className="text-red-500 text-sm text-center font-medium">{error}</div>}
          {message && <div className="text-green-500 text-sm text-center font-medium">{message}</div>}

          <div className="flex gap-4">
            <button
              type="submit"
              name="action"
              value="login"
              disabled={loading}
              className="group relative flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
            >
             {loading ? <Loader2 className="animate-spin h-5 w-5"/> : 'Log in'}
            </button>
            <button
              type="submit"
              name="action"
              value="signup"
              disabled={loading}
              className="group relative flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              Sign up
            </button>
          </div>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-white px-2 text-gray-500">Or continue with</span>
          </div>
        </div>

        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          type="button"
          className="flex w-full items-center justify-center gap-2 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus-visible:outline-offset-0 disabled:opacity-50"
        >
          <svg className="h-5 w-5" aria-hidden="true" viewBox="0 0 24 24">
            <path
              d="M12.0003 20.41c4.6483 0 8.0863-3.238 8.0863-8.238 0-.755-.078-1.311-.21-1.84h-7.876v3.472h4.526c-.232 1.488-1.558 4.29-4.526 4.29-2.732 0-4.963-2.22-4.963-4.954s2.231-4.954 4.963-4.954c1.545 0 2.916.638 3.792 1.464l2.67-2.67c-1.748-1.66-4.04-2.67-6.462-2.67-5.126 0-9.284 4.158-9.284 9.284s4.158 9.284 9.284 9.284z"
              fill="#4285F4"
            />
            <path
              d="M3.5705 7.6845c-.482.937-.755 2.01-.755 3.1655s.273 2.228.755 3.1655l2.978-2.316c-.21-.637-.327-1.327-.327-2.0495s.117-1.412.327-2.05l-2.978-2.3155z"
              fill="#FBBC05"
            />
            <path
              d="M12.0003 4.909c2.515 0 4.09 1.637 4.09 1.637l2.695-2.694c0 0-2.036-2.545-6.785-2.545-3.868 0-7.23 2.21-8.707 5.378l2.978 2.316c.712-2.083 2.684-3.592 5.009-3.592.74 0 1.442.13 2.08.36.002-.002-1.36-1.07-1.36-1.07z"
              fill="#EA4335"
            />
            <path
              d="M12.0003 19.09c-2.253 0-4.183-1.428-4.925-3.411l-2.978 2.316c1.55 3.257 4.909 5.485 8.799 5.485 3.497 0 6.075-1.758 7.378-4.19l-3.328-1.921c-.815 1.135-2.185 1.72-4.158 1.72z"
              fill="#34A853"
            />
          </svg>
          <span className="text-sm font-semibold leading-6">Google</span>
        </button>
      </div>
    </div>
  )
}
