'use client'

import { useMemo, useState } from "react"
import { BookMarked, ChevronLeft, Compass, ShieldCheck } from "lucide-react"
import Link from "next/link"
import SourcePanel from "./SourcePanel"
import ChatInterface from "./ChatInterface"

const priorityCards = [
  {
    title: "반복 강조 개념 우선 복습",
    level: "높음",
    action: "최근 3회차 강의에서 반복된 정의를 교재 핵심 섹션과 함께 먼저 확인하세요.",
  },
  {
    title: "오답 유도 포인트 정리",
    level: "중간",
    action: "예외 조건/단위/부호 관련 함정을 별도 노트로 정리하세요.",
  },
  {
    title: "연결 단원 예습",
    level: "낮음",
    action: "다음 주차와 연결된 단원의 도입부 개념만 미리 읽어두세요.",
  },
]

export default function DashboardLayout({ subject }: { subject: any }) {
  const [tab, setTab] = useState<"sources" | "guidance" | "policy">("sources")

  const title = useMemo(() => `${subject.name} 학습 워크스페이스`, [subject.name])

  return (
    <div className="th-shell space-y-5">
      <section className="th-card">
        <Link href="/dashboard" className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-foreground/70">
          <ChevronLeft className="h-3.5 w-3.5" /> 과목 목록
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-foreground/70">업로드 → 분석 → 우선순위 학습까지 한 번에 진행합니다.</p>
      </section>

      <div className="grid grid-cols-3 gap-2 rounded-2xl border border-white/10 bg-white/5 p-1.5 backdrop-blur">
        <button
          onClick={() => setTab("sources")}
          className={`rounded-xl px-2 py-2.5 text-xs font-semibold transition ${tab === "sources" ? "bg-white/15 text-foreground" : "text-foreground/70 hover:bg-white/5"}`}
        >
          자료
        </button>
        <button
          onClick={() => setTab("guidance")}
          className={`rounded-xl px-2 py-2.5 text-xs font-semibold transition ${tab === "guidance" ? "bg-white/15 text-foreground" : "text-foreground/70 hover:bg-white/5"}`}
        >
          우선순위
        </button>
        <button
          onClick={() => setTab("policy")}
          className={`rounded-xl px-2 py-2.5 text-xs font-semibold transition ${tab === "policy" ? "bg-white/15 text-foreground" : "text-foreground/70 hover:bg-white/5"}`}
        >
          안전정책
        </button>
      </div>

      {tab === "sources" && (
        <section className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <SourcePanel subjectId={subject.subject_id} />
        </section>
      )}

      {tab === "guidance" && (
        <section className="space-y-3">
          {priorityCards.map((card) => (
            <article key={card.title} className="th-card">
              <p className="text-xs font-semibold text-primary">우선순위 {card.level}</p>
              <h2 className="mt-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Compass className="h-4 w-4" />
                {card.title}
              </h2>
              <p className="mt-2 text-sm text-foreground/70">{card.action}</p>
            </article>
          ))}
          <ChatInterface />
        </section>
      )}

      {tab === "policy" && (
        <section className="th-card">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <ShieldCheck className="h-4 w-4 text-primary" /> 저작권/출력 정책
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-foreground/70">
            <li className="flex items-start gap-2">
              <BookMarked className="mt-0.5 h-4 w-4 text-primary" />
              교재 원문 장문 제공 및 재구성 요약은 차단됩니다.
            </li>
            <li className="flex items-start gap-2">
              <BookMarked className="mt-0.5 h-4 w-4 text-primary" />
              결과는 페이지/앵커/타임코드 기반 근거 위치를 중심으로 제공합니다.
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
