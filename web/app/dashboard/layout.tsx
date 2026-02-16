import type { ReactNode } from "react"
import Link from "next/link"
import { Home } from "lucide-react"
import { createClient } from "@/utils/supabase/server"
import { signout } from "../login/actions"

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  return (
    <div className="min-h-screen pb-16">
      <header className="sticky top-0 z-20 border-b border-border bg-card/95 backdrop-blur">
        <div className="mobile-shell flex items-center justify-between py-3">
          <div>
            <p className="text-xs font-semibold text-primary">Thunder Navigator</p>
            <p className="text-sm font-medium text-muted-foreground">{user?.email ?? "로그인 필요"}</p>
          </div>
          <form action={signout}>
            <button className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium">로그아웃</button>
          </form>
        </div>
      </header>

      <main>{children}</main>

      <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card">
        <div className="mobile-shell grid grid-cols-2 gap-2 py-2">
          <Link href="/" className="inline-flex items-center justify-center gap-1 rounded-lg py-2 text-sm font-medium">
            <Home className="h-4 w-4" /> 홈
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-1 rounded-lg bg-secondary py-2 text-sm font-semibold text-secondary-foreground"
          >
            대시보드
          </Link>
        </div>
      </nav>
    </div>
  )
}
