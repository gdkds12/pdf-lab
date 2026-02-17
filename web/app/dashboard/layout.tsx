import type { ReactNode } from "react"
import Link from "next/link"
import { Home, LayoutGrid, LogOut } from "lucide-react"
import { createClient } from "@/utils/supabase/server"
import { signout } from "../login/actions"
import { GrainOverlay } from "@/components/grain-overlay"

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  return (
    <div className="relative min-h-screen overflow-hidden bg-background pb-20">
      <GrainOverlay />
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-20 top-10 h-72 w-72 rounded-full bg-[#1275d8]/20 blur-3xl" />
        <div className="absolute -right-16 bottom-24 h-80 w-80 rounded-full bg-[#e19136]/15 blur-3xl" />
      </div>

      <header className="sticky top-0 z-30 border-b border-white/10 bg-black/35 backdrop-blur-xl">
        <div className="th-shell flex items-center justify-between pb-4 pt-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-foreground/70">썬더 네비게이터</p>
            <p className="text-sm font-medium text-foreground">{user?.email ?? "로그인 필요"}</p>
          </div>
          <form action={signout}>
            <button className="inline-flex items-center gap-1 rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-xs font-medium text-foreground transition hover:bg-white/20">
              <LogOut className="h-3.5 w-3.5" />
              로그아웃
            </button>
          </form>
        </div>
      </header>

      <main className="relative z-10">{children}</main>

      <nav className="fixed bottom-3 left-0 right-0 z-40">
        <div className="mx-auto grid w-[min(520px,calc(100%-2rem))] grid-cols-2 gap-2 rounded-2xl border border-white/15 bg-black/40 p-2 backdrop-blur-xl">
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-1 rounded-xl py-2 text-sm font-medium text-foreground/80 transition hover:bg-white/10 hover:text-foreground"
          >
            <Home className="h-4 w-4" /> 홈
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-1 rounded-xl bg-white/15 py-2 text-sm font-semibold text-foreground"
          >
            <LayoutGrid className="h-4 w-4" />
            대시보드
          </Link>
        </div>
      </nav>
    </div>
  )
}
