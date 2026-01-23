import Link from "next/link"
import { ExternalLink, LayoutDashboard } from "lucide-react"

export function ThemeHeader() {
  return (
    <header className="border-b border-border bg-card px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg viewBox="0 0 109 113" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-6 w-6">
            <title>Supabase Logo</title>
            <path
              d="M63.7076 110.284C60.8481 113.885 55.0502 111.912 54.9813 107.314L53.9738 40.0627L99.1935 40.0627C107.384 40.0627 111.952 49.5228 106.859 55.9374L63.7076 110.284Z"
              fill="url(#supabase-paint0_linear)"
            />
            <path
              d="M63.7076 110.284C60.8481 113.885 55.0502 111.912 54.9813 107.314L53.9738 40.0627L99.1935 40.0627C107.384 40.0627 111.952 49.5228 106.859 55.9374L63.7076 110.284Z"
              fill="url(#supabase-paint1_linear)"
              fillOpacity="0.2"
            />
            <path
              d="M45.317 2.07103C48.1765 -1.53037 53.9745 0.442937 54.0434 5.041L54.4849 72.2922H9.83113C1.64038 72.2922 -2.92775 62.8321 2.1655 56.4175L45.317 2.07103Z"
              fill="#3ECF8E"
            />
            <defs>
              <linearGradient
                id="supabase-paint0_linear"
                x1="53.9738"
                y1="54.974"
                x2="94.1635"
                y2="71.8295"
                gradientUnits="userSpaceOnUse"
              >
                <stop stopColor="#249361" />
                <stop offset="1" stopColor="#3ECF8E" />
              </linearGradient>
              <linearGradient
                id="supabase-paint1_linear"
                x1="36.1558"
                y1="30.578"
                x2="54.4844"
                y2="65.0806"
                gradientUnits="userSpaceOnUse"
              >
                <stop />
                <stop offset="1" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
          <h1 className="text-lg font-semibold text-foreground">Project Thunder</h1>
        </div>
        <div className="flex items-center gap-2">
            <Link
            href="/dashboard"
            className="flex items-center gap-2 rounded-md border border-border bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
            <LayoutDashboard className="h-4 w-4" />
            <span>Dashboard</span>
            </Link>
        </div>
      </div>
    </header>
  )
}