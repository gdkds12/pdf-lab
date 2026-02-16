'use client'

import { useMemo, useState } from "react"
import { BookMarked, ChevronLeft, Compass, ShieldCheck } from "lucide-react"
import Link from "next/link"
import SourcePanel from "./SourcePanel"
import ChatInterface from "./ChatInterface"

const priorityCards = [
  {
    title: "반복 강조 개념 우선 복습",
    level: "High",
    action: "최근 3회차 강의에서 반복된 정의를 교재 핵심 섹션과 함께 먼저 확인하세요.",
  },
  {
    title: "오답 유도 포인트 정리",
    level: "Medium",
    action: "예외 조건/단위/부호 관련 함정을 별도 노트로 정리하세요.",
  },
  {
    title: "연결 단원 예습",
    level: "Low",
    action: "다음 주차와 연결된 단원의 도입부 개념만 미리 읽어두세요.",
  },
]

export default function DashboardLayout({ subject }: { subject: any }) {
  const [tab, setTab] = useState<"sources" | "guidance" | "policy">("sources")

  const title = useMemo(() => `${subject.name} 학습 워크스페이스`, [subject.name])

  return (
    <div className="mobile-shell space-y-4 py-4">
      <section className="surface p-4">
        <Link href="/dashboard" className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
          <ChevronLeft className="h-3.5 w-3.5" /> 과목 목록
        </Link>
        <h1 className="text-lg font-bold">{title}</h1>
        <p className="mt-1 text-xs text-muted-foreground">업로드 → 분석 → 우선순위 학습까지 모바일 기준으로 빠르게 진행합니다.</p>
      </section>

      <div className="grid grid-cols-3 gap-2 rounded-xl bg-muted p-1">
        <button
          onClick={() => setTab("sources")}
          className={`rounded-lg px-2 py-2 text-xs font-semibold ${tab === "sources" ? "bg-card" : "text-muted-foreground"}`}
        >
          자료
        </button>
        <button
          onClick={() => setTab("guidance")}
          className={`rounded-lg px-2 py-2 text-xs font-semibold ${tab === "guidance" ? "bg-card" : "text-muted-foreground"}`}
        >
          우선순위
        </button>
        <button
          onClick={() => setTab("policy")}
          className={`rounded-lg px-2 py-2 text-xs font-semibold ${tab === "policy" ? "bg-card" : "text-muted-foreground"}`}
        >
          안전정책
        </button>
      </div>

      {tab === "sources" && (
        <section className="surface overflow-hidden">
          <SourcePanel subjectId={subject.subject_id} />
        </section>
      )}

      {tab === "guidance" && (
        <section className="space-y-3">
          {priorityCards.map((card) => (
            <article key={card.title} className="surface p-4">
              <p className="text-xs font-semibold text-primary">Priority {card.level}</p>
              <h2 className="mt-1 flex items-center gap-2 text-sm font-semibold">
                <Compass className="h-4 w-4" />
                {card.title}
              </h2>
              <p className="mt-2 text-xs text-muted-foreground">{card.action}</p>
            </article>
          ))}
          <ChatInterface />
        </section>
      )}

      {tab === "policy" && (
        <section className="surface p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" /> 저작권/출력 정책
          </h2>
          <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
            <li className="flex items-start gap-2">
              <BookMarked className="mt-0.5 h-4 w-4 text-primary" />
              교재 원문 장문 제공 및 재구성 요약은 차단됩니다.
            </li>
            <li className="flex items-start gap-2">
              <BookMarked className="mt-0.5 h-4 w-4 text-primary" />
              결과는 page/anchor/timecode 기반 근거 위치를 중심으로 제공합니다.
            </li>
            <li className="flex items-start gap-2">
              <BookMarked className="mt-0.5 h-4 w-4 text-primary" />
              업로드 파일은 세션 정책에 따라 최소 보관 후 삭제됩니다.
            </li>
          </ul>
        </section>
      )}
    </div>
  )
}
