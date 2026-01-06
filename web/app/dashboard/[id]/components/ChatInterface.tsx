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
    <div className="flex h-full flex-col bg-gray-50">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-6 rounded-full bg-white p-4 shadow-sm">
                <Sparkles className="h-8 w-8 text-indigo-600" />
            </div>
            <h2 className="text-2xl font-semibold text-gray-900">무엇이든 물어보세요</h2>
            <p className="mt-2 text-gray-500 max-w-md">
              업로드한 교재와 오디오를 바탕으로 답변해 드립니다.
            </p>
            
            <div className="mt-8 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 hover:bg-gray-50 hover:border-indigo-200 transition">
                핵심 내용 요약해줘
              </button>
              <button className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 hover:bg-gray-50 hover:border-indigo-200 transition">
                퀴즈 만들어줘
              </button>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`rounded-2xl px-5 py-3.5 max-w-[80%] ${
                  msg.role === 'user' 
                    ? 'bg-indigo-600 text-white rounded-br-sm' 
                    : 'bg-white text-gray-900 shadow-sm ring-1 ring-gray-200 rounded-bl-sm'
                }`}>
                  <p className="text-sm md:text-base leading-relaxed">{msg.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Suggestion Chips (Optional, can be placed above input) */}

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-200">
        <form onSubmit={handleSubmit} className="mx-auto max-w-3xl relative">
          <div className="relative flex items-center rounded-2xl border border-gray-300 bg-white shadow-sm focus-within:border-indigo-600 focus-within:ring-1 focus-within:ring-indigo-600">
             <button type="button" className="p-3 text-gray-400 hover:text-gray-600"> 
                 <Paperclip className="h-5 w-5"/>
             </button>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="질문을 입력하세요..."
              className="flex-1 w-full border-0 bg-transparent py-4 pl-2 pr-12 text-gray-900 placeholder:text-gray-400 focus:ring-0 sm:text-sm sm:leading-6"
            />
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="absolute right-2 p-2 rounded-lg bg-indigo-600 text-white disabled:bg-gray-200 disabled:text-gray-400 transition"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
        <div className="mt-2 text-center text-xs text-gray-400">
            Project Thunder는 실수를 할 수 있습니다. 중요한 정보는 확인해 주세요.
        </div>
      </div>
    </div>
  )
}
