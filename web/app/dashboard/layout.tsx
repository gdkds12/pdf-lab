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
    <div className="flex min-h-screen w-full bg-white font-sans antialiased">
      {/* Sidebar - Mini Rail Style */}
      <aside className="hidden w-[60px] flex-col border-r border-gray-200 bg-white md:flex items-center">
        <div className="flex h-14 items-center justify-center w-full border-b border-gray-200">
          <Link className="flex items-center justify-center text-gray-900" href="/">
            <Package2 className="h-6 w-6" />
          </Link>
        </div>
        
        <div className="flex flex-1 flex-col gap-4 py-4 w-full items-center">
            <Link
              href="/dashboard"
              className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors border border-emerald-100 shadow-sm"
              title="Dashboard"
            >
              <LayoutDashboard className="h-5 w-5" />
            </Link>
        </div>

        <div className="mt-auto border-t border-gray-200 p-2 w-full flex flex-col items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 border border-gray-200 text-xs font-bold text-gray-700 mb-2 cursor-help" title={user?.email || 'User'}>
                {user?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <form action={signout}>
                <Button variant="ghost" className="h-10 w-10 p-0 justify-center text-gray-400 hover:text-red-500 hover:bg-red-50" size="sm" title="Sign Out">
                    <LogOut className="h-5 w-5" />
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
