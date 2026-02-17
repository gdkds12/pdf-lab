'use client'

import { Send, ShieldCheck } from "lucide-react"
import { useState } from "react"

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

const BLOCKED_KEYWORDS = ['원문', '본문', '교재 내용 전체', 'pdf 원문', 'textbook full']

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim()) return

    const userInput = inputValue.trim()
    const blocked = BLOCKED_KEYWORDS.some((keyword) => userInput.toLowerCase().includes(keyword.toLowerCase()))

    const assistantMessage: ChatMessage = blocked
      ? {
          role: 'assistant',
          content:
            '원문/본문 제공 요청은 허용되지 않습니다. 리포트 결과와 근거 위치(page/anchor/timecode)를 기준으로 질문해 주세요.',
        }
      : {
          role: 'assistant',
          content:
            '좋아요. 현재 대화는 분석 결과물(우선순위, confidence, citation 위치)만 기준으로 답변합니다. 질문하신 항목을 학습 액션으로 재정리해 드릴게요.',
        }

    setMessages((prev) => [...prev, { role: 'user', content: userInput }, assistantMessage])
    setInputValue("")
  }

  return (
    <section className="th-card">
      <h2 className="text-sm font-semibold text-foreground">결과 기반 대화</h2>
      <p className="mt-1 flex items-start gap-2 text-xs text-foreground/70">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 text-primary" />
        교재 원문 없이 리포트 결과/근거 위치만으로 대화합니다.
      </p>

      <div className="mt-3 max-h-56 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/25 p-3">
        {messages.length === 0 ? (
          <p className="text-xs text-foreground/60">
            예시: "우선순위 High 1번을 이번 주 2시간 계획으로 쪼개줘"
          </p>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={`${msg.role}-${idx}`}
              className={`rounded-lg px-3 py-2 text-xs ${msg.role === 'user' ? 'border border-white/10 bg-white/5 text-foreground' : 'bg-primary/20 text-primary-foreground'}`}
            >
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide opacity-70">
                {msg.role === 'user' ? 'You' : 'Navigator'}
              </span>
              {msg.content}
            </div>
          ))
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex items-center gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="결과물 기반으로 질문하세요"
          className="w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-foreground placeholder:text-foreground/40 focus:border-primary focus:outline-none"
        />
        <button
          type="submit"
          disabled={!inputValue.trim()}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </section>
  )
}
