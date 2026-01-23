'use client'

import { Send, Sparkles, Paperclip } from "lucide-react"
import { useState } from "react"

export default function ChatInterface() {
  const [messages, setMessages] = useState<any[]>([]) 
  const [inputValue, setInputValue] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim()) return
    
    // 임시 메시지 추가
    setMessages([...messages, { role: 'user', content: inputValue }])
    setInputValue("")
  }

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Messages Area - Supabase SQL Editor Style */}
      <div className="flex-1 overflow-y-auto font-mono text-sm">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center p-8">
            <div className="max-w-md space-y-4">
                <div className="rounded border border-gray-200 bg-gray-50 p-6 text-left">
                    <h3 className="font-semibold text-gray-900 mb-2">Supabase AI Assistant</h3>
                    <p className="text-gray-500 mb-4">
                        Upload some PDFs or Audio files on the left, then ask me anything about the content.
                    </p>
                    <div className="space-y-2">
                        <button className="block w-full text-left px-3 py-2 rounded bg-white border border-gray-200 hover:border-emerald-500 hover:text-emerald-600 transition truncate text-xs">
                           → Summarize the key concepts from the lecture
                        </button>
                        <button className="block w-full text-left px-3 py-2 rounded bg-white border border-gray-200 hover:border-emerald-500 hover:text-emerald-600 transition truncate text-xs">
                           → Generate 5 quiz questions based on the PDF
                        </button>
                    </div>
                </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex border-b border-gray-100 ${msg.role === 'user' ? 'bg-white' : 'bg-gray-50'}`}>
                <div className="flex w-full max-w-5xl mx-auto py-6 px-4 gap-6">
                    <div className="flex-shrink-0 w-8">
                        {msg.role === 'user' ? (
                            <div className="w-6 h-6 rounded bg-emerald-600 flex items-center justify-center text-white text-xs font-bold">U</div>
                        ) : (
                             <div className="w-6 h-6 rounded bg-gray-600 flex items-center justify-center text-white text-xs font-bold">AI</div>
                        )}
                    </div>
                    <div className="flex-1 space-y-2">
                        <div className="font-semibold text-xs uppercase tracking-wider text-gray-500">
                            {msg.role === 'user' ? 'User' : 'Assistant'}
                        </div>
                        <div className="prose prose-sm prose-emerald max-w-none text-gray-800 leading-relaxed whitespace-pre-wrap">
                            {msg.content}
                        </div>
                    </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input Area - Fixed Bottom */}
      <div className="border-t border-gray-200 bg-white p-4">
        <div className="max-w-5xl mx-auto">
            <form onSubmit={handleSubmit} className="relative">
            <div className="relative flex items-center rounded-md border border-gray-300 bg-white shadow-sm focus-within:border-emerald-600 focus-within:ring-1 focus-within:ring-emerald-600">
                <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask a question about your sources..."
                className="flex-1 w-full border-0 bg-transparent py-3 pl-4 pr-12 text-gray-900 placeholder:text-gray-400 focus:ring-0 sm:text-sm font-mono"
                />
                <button
                type="submit"
                disabled={!inputValue.trim()}
                className="absolute right-2 p-1.5 rounded bg-gray-100 text-gray-500 hover:bg-emerald-600 hover:text-white disabled:bg-gray-50 disabled:text-gray-300 transition"
                >
                <Send className="h-4 w-4" />
                </button>
            </div>
            </form>
            <div className="mt-2 text-center text-[10px] text-gray-400 font-mono">
                AI generated content can be inaccurate. Verify important information.
            </div>
        </div>
      </div>
    </div>
  )
}
