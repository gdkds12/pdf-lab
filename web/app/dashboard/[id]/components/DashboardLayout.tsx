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
    <div className="flex h-full w-full bg-background overflow-hidden">
      
      {/* 2nd Column Sidebar - Project Explorer / Sources */}
      {/* This renders directly next to the Global Rail (which is in the parent layout) */}
      <aside className="w-72 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col z-20">
         <SourcePanel subjectId={subject.subject_id} />
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 bg-white relative z-10 h-full">
         
          {/* Top Bar / Breadcrumbs - Now sitting ABOVE the Chat, inside the main content area */}
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-100 px-6 bg-white">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="font-semibold text-gray-900 text-lg">{subject.name}</span>
              <span className="text-gray-300 mx-2">/</span>
              <span className="text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded text-xs">Analysis</span>
            </div>
            
            <button 
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className={`p-2 rounded-md transition-colors ${isSettingsOpen ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'}`}
                title="Settings"
            >
                <Settings className="h-5 w-5" />
            </button>
          </div>

          <main className="flex-1 min-h-0 overflow-hidden relative">
              <ChatInterface />
          </main>
      </div>

      {/* Right Sidebar - Settings (Overlays or pushes?) - keep pushing for now */}
      {isSettingsOpen && (
           <aside className="w-80 flex-shrink-0 border-l border-gray-200 bg-white shadow-xl z-30">
              <SettingsPanel />
           </aside>
      )}
    </div>
  )
}
