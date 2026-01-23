'use client'

import { useState } from "react"
import Link from "next/link"
import { Settings, ChevronRight, Home } from "lucide-react"
import SourcePanel from "./SourcePanel"
import ChatInterface from "./ChatInterface"
import SettingsPanel from "./SettingsPanel" 

export default function DashboardLayout({ subject }: { subject: any }) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  return (
    <div className="flex flex-col h-full w-full bg-background">
      {/* Top Bar / Breadcrumbs - Supabase Style */}
      <div className="flex h-12 items-center justify-between border-b px-4 bg-white/50 backdrop-blur-sm">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/dashboard" className="flex items-center gap-1 hover:text-foreground transition-colors text-gray-500 hover:text-gray-900">
            <Home className="h-4 w-4" />
          </Link>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-900 transition-colors">
            Dashboard
          </Link>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <span className="font-medium text-gray-900">{subject.name}</span>
        </div>
        
        <button 
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className={`p-2 rounded-md transition-colors ${isSettingsOpen ? 'bg-indigo-50 text-indigo-600' : 'text-gray-500 hover:bg-gray-100'}`}
            title="Toggle Settings"
        >
            <Settings className="h-4 w-4" />
        </button>
      </div>

      {/* Main Content Area - Grid Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Sources */}
        <aside className="w-80 flex-shrink-0 flex flex-col">
            <SourcePanel subjectId={subject.subject_id} />
        </aside>

        {/* Center - Chat */}
        <main className="flex-1 min-w-0 bg-white relative">
            <ChatInterface />
        </main>

        {/* Right Sidebar - Settings (Collapsible) */}
        {isSettingsOpen && (
             <aside className="w-80 flex-shrink-0 border-l border-gray-200 bg-white shadow-xl z-10">
                <SettingsPanel />
             </aside>
        )}
      </div>
    </div>
  )
}
