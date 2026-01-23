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
      {/* Sidebar */}
      <aside className="hidden w-64 flex-col border-r bg-card md:flex">
        <div className="flex h-14 items-center border-b px-6">
          <Link className="flex items-center gap-2 font-semibold" href="/">
            <Package2 className="h-6 w-6" />
            <span className="">Project Thunder</span>
          </Link>
        </div>
        <div className="flex flex-1 flex-col gap-2 p-4">
          <div className="flex flex-col gap-1">
            <Link
              href="/dashboard"
              className="flex items-center gap-3 rounded-lg bg-muted px-3 py-2 text-primary transition-all hover:text-primary"
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Link>
          </div>
        </div>
        <div className="mt-auto border-t p-4">
            <div className="flex items-center gap-3 px-2 py-2">
                <div className="flex flex-col">
                    <span className="text-sm font-medium">{user?.email?.split('@')[0]}</span>
                    <span className="text-xs text-muted-foreground">Free Plan</span>
                </div>
            </div>
            <form action={signout}>
                <Button variant="ghost" className="w-full justify-start gap-2 mt-2" size="sm">
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
        <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
