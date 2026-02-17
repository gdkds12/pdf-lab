'use client'

import { useEffect, useState } from "react"
import { createClient } from "@/utils/supabase/client"
import { Loader2, BookOpen, AlertTriangle, Lightbulb } from "lucide-react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

interface ReportViewerModalProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  title: string
}

type ReportData = {
  warnings?: string[]
  professor_mentioned?: ReportItem[]
  likely?: ReportItem[]
  trap_warnings?: ReportItem[]
}

type ReportItem = {
  title: string
  why: string
  confidence: number
  citations: {
    chunk_id: string
    reason?: string
    page_start?: number
    page_end?: number
  }[]
}

export default function ReportViewerModal({ isOpen, onClose, sessionId, title }: ReportViewerModalProps) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const supabase = createClient()

  useEffect(() => {
    if (!isOpen || !sessionId) return

    const fetchReport = async () => {
      setLoading(true)
      setError(null)

      try {
        const { data, error: fetchError } = await supabase
          .from('session_reports')
          .select('report_json')
          .eq('session_id', sessionId)
          .single()

        if (fetchError) throw fetchError
        if (!data?.report_json) throw new Error('리포트를 찾을 수 없습니다.')

        setReport(data.report_json as ReportData)
      } catch (err: unknown) {
        console.error(err)
        if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('리포트 로딩 실패')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchReport()
  }, [isOpen, sessionId])

  const professorMentioned = report?.professor_mentioned ?? []
  const likelyItems = report?.likely ?? []
  const trapWarnings = report?.trap_warnings ?? []
  const warnings = report?.warnings ?? []

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[min(100vw-1.5rem,72rem)] max-w-5xl border-white/15 bg-[#0d121a]/95 p-0 text-foreground">
        <DialogHeader className="border-b border-white/10 px-5 py-4 sm:px-6">
          <DialogTitle className="text-lg font-semibold">통합 분석 리포트</DialogTitle>
          <p className="text-xs text-foreground/70">{title}</p>
        </DialogHeader>

        <div className="max-h-[72vh] overflow-y-auto px-5 py-5 sm:px-6">
          {loading ? (
            <div className="flex h-56 flex-col items-center justify-center gap-3">
              <Loader2 className="h-7 w-7 animate-spin text-primary" />
              <span className="text-sm text-foreground/70">리포트를 불러오는 중입니다...</span>
            </div>
          ) : error ? (
            <div className="flex h-56 flex-col items-center justify-center gap-2 text-red-300">
              <AlertTriangle className="h-7 w-7" />
              <p className="text-sm font-semibold">{error}</p>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-8">
              {warnings.length > 0 && (
                <section className="rounded-xl border border-amber-300/35 bg-amber-500/10 px-4 py-3">
                  <h3 className="text-sm font-semibold text-amber-100">검증/보호 안내</h3>
                  <ul className="mt-2 space-y-1 text-xs text-amber-100/90">
                    {warnings.map((warning, idx) => (
                      <li key={`${warning}-${idx}`}>- {warning}</li>
                    ))}
                  </ul>
                </section>
              )}

              <section>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-lg bg-red-400/20 p-2 text-red-300">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">교수님 강조 (출제 유력)</h3>
                </div>
                <div className="grid gap-4">
                  {professorMentioned.length === 0 ? (
                    <p className="pl-2 text-sm italic text-foreground/60">특이 강조 사항 없음</p>
                  ) : (
                    professorMentioned.map((item, idx) => <ReportCard key={`pm-${idx}`} item={item} type="high" />)
                  )}
                </div>
              </section>

              <div className="h-px bg-white/10" />

              <section>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-lg bg-blue-400/20 p-2 text-blue-300">
                    <BookOpen className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">출제 예상 내용</h3>
                </div>
                <div className="grid gap-4">
                  {likelyItems.length === 0 ? (
                    <p className="pl-2 text-sm italic text-foreground/60">예상 내용 없음</p>
                  ) : (
                    likelyItems.map((item, idx) => <ReportCard key={`likely-${idx}`} item={item} type="normal" />)
                  )}
                </div>
              </section>

              <div className="h-px bg-white/10" />

              <section>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-lg bg-yellow-400/20 p-2 text-yellow-200">
                    <Lightbulb className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">함정 주의 / 오개념 경고</h3>
                </div>
                <div className="grid gap-4">
                  {trapWarnings.length === 0 ? (
                    <p className="pl-2 text-sm italic text-foreground/60">특별한 주의사항 없음</p>
                  ) : (
                    trapWarnings.map((item, idx) => <ReportCard key={`trap-${idx}`} item={item} type="warning" />)
                  )}
                </div>
              </section>
            </div>
          )}
        </div>

        <DialogFooter className="border-t border-white/10 bg-black/25 px-5 py-3 sm:px-6">
          <button
            onClick={onClose}
            className="rounded-lg border border-white/15 bg-white/10 px-4 py-2 text-sm font-medium text-foreground transition hover:bg-white/20"
          >
            닫기
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ReportCard({ item, type }: { item: ReportItem; type: 'high' | 'normal' | 'warning' }) {
  const borderColor =
    type === 'high' ? 'border-red-300/40' : type === 'warning' ? 'border-yellow-300/40' : 'border-blue-300/30'
  const bgColor = type === 'high' ? 'bg-red-500/10' : type === 'warning' ? 'bg-yellow-500/10' : 'bg-white/5'

  return (
    <article className={`rounded-xl border ${borderColor} ${bgColor} p-5 shadow-sm transition hover:bg-white/10`}>
      <div className="mb-2 flex items-start justify-between">
        <h4 className="text-base font-semibold text-foreground">{item.title}</h4>
        {item.confidence ? (
          <span className="rounded border border-white/10 bg-black/20 px-1.5 py-0.5 font-mono text-xs text-foreground/70">
            Conf: {(item.confidence * 100).toFixed(0)}%
          </span>
        ) : null}
      </div>
      <p className="mb-3 text-sm leading-relaxed text-foreground/80">{item.why}</p>

      {item.citations && item.citations.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="flex items-center gap-1 text-xs font-semibold text-foreground/60">
            <BookOpen className="h-3 w-3" /> 관련 교재 참조
          </p>
          {item.citations.map((citation, index) => (
            <div key={`${citation.chunk_id}-${index}`} className="rounded-md border border-white/10 bg-black/25 p-2 text-xs transition hover:border-primary/50">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="inline-flex flex-shrink-0 items-center rounded border border-white/10 bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-foreground/80">
                  {citation.page_start ? (
                    <>p.{citation.page_start}{citation.page_end && citation.page_end !== citation.page_start ? `-${citation.page_end}` : ''}</>
                  ) : (
                    'Reference'
                  )}
                </span>
                {citation.reason ? <span className="truncate font-medium text-primary">{citation.reason}</span> : null}
              </div>
              <p className="border-l-2 border-primary/40 pl-2 text-[11px] leading-relaxed text-foreground/60">
                원문 텍스트는 제공되지 않으며 위치 정보만 제공합니다.
              </p>
            </div>
          ))}
        </div>
      )}
    </article>
  )
}
