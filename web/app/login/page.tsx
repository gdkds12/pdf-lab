'use client'

import { login, signup } from './actions'
import { useState } from 'react'
import { Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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
      </div>
    </div>
  )
}
