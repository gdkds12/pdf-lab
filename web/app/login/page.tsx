'use client'

import { login, signup, signInWithGoogle } from './actions'
import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
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
    <div className="flex h-screen w-full items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Project Thunder</CardTitle>
          <CardDescription>
            Enter your email below to login to your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" type="email" placeholder="m@example.com" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" type="password" required />
            </div>
            {error && <p className="text-sm font-medium text-destructive">{error}</p>}
            {message && <p className="text-sm font-medium text-green-500">{message}</p>}
            <div className="flex gap-2 w-full pt-2">
                <Button className="w-full" type="submit" name="action" value="login" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Sign In
                </Button>
                <Button className="w-full" variant="outline" type="submit" name="action" value="signup" disabled={loading}>
                    Sign Up
                </Button>
            </div>
          </form>
          
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or continue with
              </span>
            </div>
          </div>
          <Button variant="outline" type="button" className="w-full" onClick={handleGoogleLogin} disabled={loading}>
            <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
            <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
            </svg>
            Google
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
