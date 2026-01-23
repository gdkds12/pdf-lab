import type { ReactNode } from "react"
import Link from "next/link"
import { Package2, LayoutDashboard, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { createClient } from "@/utils/supabase/server"
import { signout } from "../login/actions"

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Sidebar - Mini Rail Style when needed, but here sticking to standard wide sidebar for consistency */}
      <aside className="hidden w-64 flex-col border-r bg-slate-950 text-slate-300 md:flex">
        <div className="flex h-12 items-center border-b border-slate-800 px-6">
          <Link className="flex items-center gap-2 font-semibold text-white" href="/">
            <Package2 className="h-6 w-6" />
            <span className="">Project Thunder</span>
          </Link>
        </div>
        <div className="flex flex-1 flex-col gap-2 p-2">
          <div className="flex flex-col gap-1">
            <Link
              href="/dashboard"
              className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-800 hover:text-white transition-colors text-white bg-slate-800"
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Link>
          </div>
        </div>
        <div className="mt-auto border-t border-slate-800 p-4">
            <div className="flex items-center gap-3 px-2 py-2">
                <div className="flex flex-col">
                    <span className="text-sm font-medium text-white">{user?.email?.split('@')[0]}</span>
                    <span className="text-xs text-slate-500">Free Plan</span>
                </div>
            </div>
            <form action={signout}>
                <Button variant="ghost" className="w-full justify-start gap-2 mt-2 text-slate-400 hover:text-white hover:bg-slate-800" size="sm">
                    <LogOut className="h-4 w-4" />
                    Sign Out
                </Button>
            </form>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center gap-4 border-b bg-card px-6 lg:h-[60px] md:hidden">
          <Link className="flex items-center gap-2 font-semibold" href="#">
            <Package2 className="h-6 w-6" />
            <span className="">Project Thunder</span>
          </Link>
        </header>
        <main className="flex flex-1 flex-col overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
