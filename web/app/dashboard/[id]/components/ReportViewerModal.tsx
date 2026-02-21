'use client'

import { useEffect, useState } from "react"
import { createClient } from "@/utils/supabase/client"
import { Loader2, BookOpen, AlertTriangle, Lightbulb, Headphones, ListOrdered } from "lucide-react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

interface ReportViewerModalProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  title: string
}

type ProofRef = {
  signal_id: string
  audio_chunk_id?: string | null
  t0_sec: number
  t1_sec: number
  note?: string | null
}

type ReferenceRef = {
  chunk_id: string
  reason?: string | null
  source_id?: string | null
  page_start?: number | null
  page_end?: number | null
  page_type?: string | null
  anchor_path?: string[] | null
}

type QueueItem = {
  rank?: number
  title: string
  problem_id?: string | null
  why: string
  study_action: string
  importance: number
  importance_score: number
  proof_refs: ProofRef[]
  references: ReferenceRef[]
}

type ReportData = {
  warnings?: string[]
  recommendation_queue?: QueueItem[]
  recommendation_queue_confirmed?: QueueItem[]
  recommendation_queue_candidates?: QueueItem[]
}

function formatSecRange(t0: number, t1: number) {
  const toMmSs = (sec: number) => {
    const s = Math.max(0, Math.floor(sec))
    const mm = Math.floor(s / 60)
    const ss = s % 60
    return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
  }
  return `${toMmSs(t0)} ~ ${toMmSs(t1)}`
}

function formatReference(ref: ReferenceRef) {
  if (typeof ref.page_start === 'number') {
    const prefix = ref.page_type === 'pdf_page' ? 'PDF p.' : 'p.'
    if (typeof ref.page_end === 'number' && ref.page_end !== ref.page_start) {
      return `${prefix}${ref.page_start}-${ref.page_end}`
    }
    return `${prefix}${ref.page_start}`
  }

  if (Array.isArray(ref.anchor_path) && ref.anchor_path.length > 0) {
    return ref.anchor_path.join(' > ')
  }

  return '교재 참조'
}

function parseProofNote(note?: string | null) {
  if (!note) return { noteText: null as string | null, fileName: null as string | null }
  const m = note.match(/파일\s*:\s*([^|]+)/)
  const fileName = m?.[1]?.trim() || null
  const noteText = note.replace(/\|?\s*파일\s*:\s*[^|]+/, '').trim() || null
  return { noteText, fileName }
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

  const rawWarnings = report?.warnings ?? []
  const warnings = rawWarnings.filter((w) => {
    if (!w) return false
    // Reduce noisy validation internals in UI
    return !(
      w.startsWith('추천 항목: title/why 누락') ||
      w.startsWith('검증 제외 항목:') ||
      w.startsWith('검증 제외 사유:') ||
      w.startsWith('검증 제외 예시:')
    )
  })
  const hasNoSignalWarning = rawWarnings.some((w) => w.includes('신호(signals)가 없어'))
  const confirmedQueue = report?.recommendation_queue_confirmed ?? []
  const candidateQueue = report?.recommendation_queue_candidates ?? []
  const queue = report?.recommendation_queue ?? []
  const hasSplitQueues = confirmedQueue.length > 0 || candidateQueue.length > 0

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[min(100vw-1.5rem,72rem)] max-w-5xl border-white/15 bg-[#0d121a]/95 p-0 text-foreground">
        <DialogHeader className="border-b border-white/10 px-5 py-4 sm:px-6">
          <DialogTitle className="text-lg font-semibold">추천 문제 큐 리포트</DialogTitle>
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
            <div className="mx-auto max-w-4xl space-y-6">
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
                <div className="mb-3 flex items-center gap-2">
                  <div className="rounded-lg bg-primary/20 p-2 text-primary">
                    <ListOrdered className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">추천 문제 큐</h3>
                </div>

                {(hasSplitQueues ? (confirmedQueue.length + candidateQueue.length) : queue.length) === 0 ? (
                  <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-5 text-sm text-foreground/70">
                    {hasNoSignalWarning
                      ? '이 세션은 추출된 신호가 없어 추천을 생성하지 못했습니다. 해당 오디오 파일의 인식 상태를 먼저 확인해 주세요.'
                      : '생성된 추천 항목이 없습니다. 오디오 파일을 더 추가한 뒤 다시 리포트를 생성해 주세요.'}
                  </div>
                ) : (
                  <div className="space-y-5">
                    {hasSplitQueues && (
                      <div className="grid gap-2 rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-foreground/75 md:grid-cols-2">
                        <p>확정 추천: <span className="font-semibold text-foreground">{confirmedQueue.length}개</span></p>
                        <p>후보 추천: <span className="font-semibold text-foreground">{candidateQueue.length}개</span></p>
                      </div>
                    )}

                    {((hasSplitQueues ? confirmedQueue : queue) ?? []).map((item, idx) => (
                      <article key={`confirmed-${item.title}-${idx}`} className="rounded-xl border border-emerald-300/25 bg-emerald-500/5 p-4">
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold text-emerald-300">
                              확정 {item.rank ?? idx + 1} · 중요도 {item.importance_score}점
                            </p>
                            <h4 className="mt-1 text-base font-semibold text-foreground">{item.title}</h4>
                          </div>
                          <span className="rounded border border-white/10 bg-black/20 px-1.5 py-0.5 font-mono text-xs text-foreground/70">
                            {(item.importance * 100).toFixed(0)}%
                          </span>
                        </div>

                        {item.problem_id ? (
                          <p className="mt-1 text-xs font-semibold text-primary">추천 문제: {item.problem_id}</p>
                        ) : null}
                        <p className="text-sm leading-relaxed text-foreground/80">{item.why}</p>
                        <p className="mt-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 text-xs text-primary-foreground">
                          학습 액션: {item.study_action}
                        </p>

                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                          <div className="rounded-lg border border-white/10 bg-black/25 p-3">
                            <p className="mb-2 flex items-center gap-1 text-xs font-semibold text-foreground/70">
                              <Headphones className="h-3.5 w-3.5" /> 근거 음성 구간
                            </p>
                            <div className="space-y-2">
                              {item.proof_refs?.map((proof, proofIdx) => {
                                const { noteText, fileName } = parseProofNote(proof.note)
                                return (
                                  <div key={`${proof.signal_id}-${proofIdx}`} className="rounded border border-white/10 bg-white/5 px-2 py-1.5 text-xs">
                                    <p className="font-mono text-foreground/80">{formatSecRange(proof.t0_sec, proof.t1_sec)}</p>
                                    {fileName ? <p className="mt-1 text-foreground/80">원본 파일: {fileName}</p> : null}
                                    {noteText ? <p className="mt-1 text-foreground/70">{noteText}</p> : null}
                                  </div>
                                )
                              })}
                            </div>
                          </div>

                          <div className="rounded-lg border border-white/10 bg-black/25 p-3">
                            <p className="mb-2 flex items-center gap-1 text-xs font-semibold text-foreground/70">
                              <BookOpen className="h-3.5 w-3.5" /> 교재 좌표/문제
                            </p>
                            <div className="space-y-2">
                              {item.references?.map((ref, refIdx) => (
                                <div key={`${ref.chunk_id}-${refIdx}`} className="rounded border border-white/10 bg-white/5 px-2 py-1.5 text-xs">
                                  <p className="font-mono text-foreground/80">{formatReference(ref)}</p>
                                  {Array.isArray(ref.anchor_path) && ref.anchor_path.length > 0 ? (
                                    <p className="mt-1 text-foreground/70">목차: {ref.anchor_path.join(' > ')}</p>
                                  ) : null}
                                  {ref.reason ? <p className="mt-1 text-foreground/70">{ref.reason}</p> : null}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}

                    {hasSplitQueues && candidateQueue.length > 0 && (
                      <section className="space-y-3">
                        <h4 className="text-sm font-semibold text-foreground/80">후보 추천</h4>
                        {candidateQueue.map((item, idx) => (
                          <article key={`candidate-${item.title}-${idx}`} className="rounded-xl border border-white/10 bg-white/5 p-4">
                            <p className="text-xs font-semibold text-primary">후보 {item.rank ?? idx + 1} · 중요도 {item.importance_score}점</p>
                            <h5 className="mt-1 text-sm font-semibold text-foreground">{item.title}</h5>
                            {item.problem_id ? <p className="mt-1 text-xs text-primary/90">추천 문제: {item.problem_id}</p> : null}
                            <p className="mt-1 text-xs text-foreground/75">{item.why}</p>
                          </article>
                        ))}
                      </section>
                    )}
                  </div>
                )}
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
