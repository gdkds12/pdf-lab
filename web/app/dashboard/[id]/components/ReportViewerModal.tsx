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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
            <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-xl bg-white shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">분석 리포트</h2>
                        <p className="text-sm text-gray-500">{title}</p>
                    </div>
                    <button onClick={onClose} className="rounded-full p-2 hover:bg-gray-100 transition">
                        <X className="h-5 w-5 text-gray-500" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto bg-gray-50 p-6">
                    {loading ? (
                        <div className="flex h-full items-center justify-center flex-col gap-3">
                            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
                            <span className="text-gray-500 font-medium">리포트 불러오는 중...</span>
                        </div>
                    ) : error ? (
                        <div className="flex h-full items-center justify-center text-red-500 flex-col gap-2">
                             <AlertTriangle className="h-8 w-8" />
                             <span className="font-semibold">{error}</span>
                        </div>
                    ) : report ? (
                        <div className="space-y-8 max-w-3xl mx-auto">
                            
                            {/* Section 1: Professor Mentioned (High Priority) */}
                            <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="p-2 bg-red-100 rounded-lg text-red-600">
                                        <AlertTriangle className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-gray-900">교수님 강조 (출제 유력)</h3>
                                </div>
                                <div className="grid gap-4">
                                    {report.professor_mentioned?.length === 0 ? (
                                        <p className="text-gray-500 text-sm italic pl-2">특이 강조 사항 없음</p>
                                    ) : (
                                        report.professor_mentioned?.map((item, idx) => (
                                            <ReportCard key={idx} item={item} type="high" />
                                        ))
                                    )}
                                </div>
                            </section>

                            <div className="h-px bg-gray-200" />

                            {/* Section 2: Likely */}
                            <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
                                        <BookOpen className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-gray-900">출제 예상 내용</h3>
                                </div>
                                <div className="grid gap-4">
                                     {report.likely?.length === 0 ? (
                                        <p className="text-gray-500 text-sm italic pl-2">예상 내용 없음</p>
                                    ) : (
                                        report.likely?.map((item, idx) => (
                                            <ReportCard key={idx} item={item} type="normal" />
                                        ))
                                    )}
                                </div>
                            </section>
                            
                            <div className="h-px bg-gray-200" />

                             {/* Section 3: Trap Warnings */}
                             <section>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="p-2 bg-yellow-100 rounded-lg text-yellow-600">
                                        <Lightbulb className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-bold text-gray-900">함정 주의 / 오개념 경고</h3>
                                </div>
                                <div className="grid gap-4">
                                     {report.trap_warnings?.length === 0 ? (
                                        <p className="text-gray-500 text-sm italic pl-2">특별한 주의사항 없음</p>
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
                <div className="border-t border-gray-200 bg-white p-4 flex justify-end">
                    <button 
                        onClick={onClose}
                        className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 transition"
                    >
                        닫기
                    </button>
                </div>
            </div>
        </div>
    )
}

function ReportCard({ item, type }: { item: ReportItem, type: 'high' | 'normal' | 'warning' }) {
    const borderColor = type === 'high' ? 'border-red-200' : type === 'warning' ? 'border-yellow-200' : 'border-blue-200'
    const bgColor = type === 'high' ? 'bg-red-50' : type === 'warning' ? 'bg-yellow-50' : 'bg-white'

    return (
        <div className={`rounded-xl border ${borderColor} ${bgColor} p-5 shadow-sm transition hover:shadow-md`}>
            <div className="flex justify-between items-start mb-2">
                <h4 className="font-semibold text-gray-900 text-base">{item.title}</h4>
                {item.confidence && (
                    <span className="text-xs font-mono text-gray-400 bg-white/50 px-1.5 py-0.5 rounded border border-gray-100">
                        Conf: {(item.confidence * 100).toFixed(0)}%
                    </span>
                )}
            </div>
            <p className="text-sm text-gray-700 leading-relaxed mb-3">{item.why}</p>
            
            {item.citations && item.citations.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                    {item.citations.map((c, i) => (
                        <span key={i} className="inline-flex items-center text-[10px] px-2 py-1 rounded bg-white border border-gray-200 text-gray-500">
                            {c.page_start ? (
                                <>p.{c.page_start}{c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ''}</>
                            ) : (
                                <>Ref: {c.chunk_id.substring(0, 8)}...</>
                            )}
                        </span>
                    ))}
                </div>
            )}
        </div>
    )
}
