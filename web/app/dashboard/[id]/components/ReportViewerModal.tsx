'use client'

import { useEffect, useState } from "react"
import { createClient } from "@/utils/supabase/client"
import { Loader2, X, BookOpen, AlertTriangle, Lightbulb } from "lucide-react"

// Since we don't know if shadcn is installed, I will use a custom simple modal implementation to be safe.
// If the workspace has shadcn, the user didn't mention it. I see tailwind config so I'll use standard tailwind classes.

interface ReportViewerModalProps {
    isOpen: boolean
    onClose: () => void
    sessionId: string
    title: string
}

type ReportData = {
    warnings?: string[]
    professor_mentioned: ReportItem[]
    likely: ReportItem[]
    trap_warnings: ReportItem[]
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
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const supabase = createClient()

    useEffect(() => {
        if (!isOpen) return

        const fetchReport = async () => {
            setLoading(true)
            setError(null)
            try {
                const { data, error } = await supabase
                    .from('session_reports')
                    .select('report_json')
                    .eq('session_id', sessionId)
                    .single()

                if (error) throw error
                if (!data) throw new Error("리포트를 찾을 수 없습니다.")

                setReport(data.report_json)
            } catch (err: any) {
                console.error(err)
                setError(err.message || "리포트 로딩 실패")
            } finally {
                setLoading(false)
            }
        }

        fetchReport()
    }, [isOpen, sessionId])

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm">
            <div className="flex h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-white/15 bg-[#0d121a]/95 shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
                    <div>
                        <h2 className="text-xl font-bold text-foreground">분석 리포트</h2>
                        <p className="text-sm text-foreground/70">{title}</p>
                    </div>
                    <button onClick={onClose} className="rounded-full p-2 transition hover:bg-white/10">
                        <X className="h-5 w-5 text-foreground/70" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto bg-transparent p-6">
                    {loading ? (
                        <div className="flex h-full items-center justify-center flex-col gap-3">
                            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
                            <span className="font-medium text-foreground/70">리포트 불러오는 중...</span>
                        </div>
                    ) : error ? (
                        <div className="flex h-full flex-col items-center justify-center gap-2 text-red-400">
                             <AlertTriangle className="h-8 w-8" />
                             <span className="font-semibold">{error}</span>
                        </div>
                    ) : report ? (
                        <div className="space-y-8 max-w-3xl mx-auto">
                            {report.warnings && report.warnings.length > 0 && (
                                <section className="rounded-lg border border-amber-300/40 bg-amber-500/10 px-4 py-3">
                                    <h3 className="text-sm font-semibold text-amber-200">검증/보호 안내</h3>
                                    <ul className="mt-2 space-y-1 text-xs text-amber-100/90">
                                        {report.warnings.map((w, idx) => (
                                            <li key={idx}>- {w}</li>
                                        ))}
                                    </ul>
                                </section>
                            )}
                            
                            {/* Section 1: Professor Mentioned (High Priority) */}
                            <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="rounded-lg bg-red-400/20 p-2 text-red-300">
                                        <AlertTriangle className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-foreground">교수님 강조 (출제 유력)</h3>
                                </div>
                                <div className="grid gap-4">
                                    {report.professor_mentioned?.length === 0 ? (
                                        <p className="pl-2 text-sm italic text-foreground/60">특이 강조 사항 없음</p>
                                    ) : (
                                        report.professor_mentioned?.map((item, idx) => (
                                            <ReportCard key={idx} item={item} type="high" />
                                        ))
                                    )}
                                </div>
                            </section>

                            <div className="h-px bg-white/10" />

                            {/* Section 2: Likely */}
                            <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="rounded-lg bg-blue-400/20 p-2 text-blue-300">
                                        <BookOpen className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-foreground">출제 예상 내용</h3>
                                </div>
                                <div className="grid gap-4">
                                     {report.likely?.length === 0 ? (
                                        <p className="pl-2 text-sm italic text-foreground/60">예상 내용 없음</p>
                                    ) : (
                                        report.likely?.map((item, idx) => (
                                            <ReportCard key={idx} item={item} type="normal" />
                                        ))
                                    )}
                                </div>
                            </section>
                            
                            <div className="h-px bg-white/10" />

                             {/* Section 3: Trap Warnings */}
                             <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="rounded-lg bg-yellow-400/20 p-2 text-yellow-200">
                                        <Lightbulb className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-foreground">함정 주의 / 오개념 경고</h3>
                                </div>
                                <div className="grid gap-4">
                                     {report.trap_warnings?.length === 0 ? (
                                        <p className="pl-2 text-sm italic text-foreground/60">특별한 주의사항 없음</p>
                                    ) : (
                                        report.trap_warnings?.map((item, idx) => (
                                            <ReportCard key={idx} item={item} type="warning" />
                                        ))
                                    )}
                                </div>
                            </section>

                        </div>
                    ) : null}
                </div>
                
                 {/* Footer */}
                <div className="flex justify-end border-t border-white/10 bg-black/30 p-4">
                    <button 
                        onClick={onClose}
                        className="rounded-lg border border-white/15 bg-white/10 px-4 py-2 text-sm font-medium text-foreground transition hover:bg-white/20"
                    >
                        닫기
                    </button>
                </div>
            </div>
        </div>
    )
}

function ReportCard({ item, type }: { item: ReportItem, type: 'high' | 'normal' | 'warning' }) {
    const borderColor = type === 'high' ? 'border-red-300/40' : type === 'warning' ? 'border-yellow-300/40' : 'border-blue-300/30'
    const bgColor = type === 'high' ? 'bg-red-500/10' : type === 'warning' ? 'bg-yellow-500/10' : 'bg-white/5'

    return (
        <div className={`rounded-xl border ${borderColor} ${bgColor} p-5 shadow-sm transition hover:bg-white/10`}>
            <div className="flex justify-between items-start mb-2">
                <h4 className="text-base font-semibold text-foreground">{item.title}</h4>
                {item.confidence && (
                    <span className="rounded border border-white/10 bg-black/20 px-1.5 py-0.5 font-mono text-xs text-foreground/70">
                        Conf: {(item.confidence * 100).toFixed(0)}%
                    </span>
                )}
            </div>
            <p className="mb-3 text-sm leading-relaxed text-foreground/80">{item.why}</p>
            
            {item.citations && item.citations.length > 0 && (
                <div className="mt-3 space-y-2">
                    <p className="flex items-center gap-1 text-xs font-semibold text-foreground/60">
                        <BookOpen className="h-3 w-3" /> 관련 교재 참조
                    </p>
                    {item.citations.map((c, i) => (
                        <div key={i} className="rounded-md border border-white/10 bg-black/25 p-2 text-xs transition hover:border-primary/50">
                            <div className="flex items-center gap-2 mb-1.5">
                                <span className="inline-flex flex-shrink-0 items-center rounded border border-white/10 bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-foreground/80">
                                    {c.page_start ? (
                                        <>p.{c.page_start}{c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ''}</>
                                    ) : (
                                        'Reference'
                                    )}
                                </span>
                                {c.reason && <span className="truncate font-medium text-primary">{c.reason}</span>}
                            </div>
                            <p className="border-l-2 border-primary/40 pl-2 text-[11px] leading-relaxed text-foreground/60">
                                원문 텍스트는 제공되지 않으며 위치 정보만 제공합니다.
                            </p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
