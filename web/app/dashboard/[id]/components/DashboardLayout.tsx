'use client'

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Settings, PanelRight } from "lucide-react"
import SourcePanel from "./SourcePanel"
import ChatInterface from "./ChatInterface"
import SettingsPanel from "./SettingsPanel" // 새로 만들 예정

export default function DashboardLayout({ subject }: { subject: any }) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  return (
    <div className="flex h-screen flex-col bg-white">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
        <div className="flex items-center gap-4">
          <Link 
            href="/dashboard"
            className="rounded-full p-2 text-gray-500 hover:bg-gray-100 transition"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-xs font-bold text-indigo-700">
                {subject.name.substring(0, 1)}
            </span>
            <h1 className="text-sm font-semibold text-gray-900">{subject.name}</h1>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
            <button 
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className={`rounded-md p-2 text-sm font-medium transition ${isSettingsOpen ? 'bg-indigo-50 text-indigo-600' : 'text-gray-500 hover:bg-gray-50'}`}
            >
                <div className="flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    <span className="hidden sm:inline">설정</span>
                </div>
            </button>
        </div>
      </header>

      {/* Main Content Area - Grid Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Sources */}
        <aside className="w-80 flex-shrink-0 hidden md:block">
            <SourcePanel subjectId={subject.subject_id} />
        </aside>

        {/* Center - Chat */}
        <main className="flex-1 min-w-0">
            <ChatInterface />
        </main>

        {/* Right Sidebar - Settings (Collapsible) */}
        {isSettingsOpen && (
             <aside className="w-80 flex-shrink-0 border-l border-gray-200 bg-white">
                <SettingsPanel />
             </aside>
        )}
      </div>
    </div>
  )
}
