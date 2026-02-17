'use client'

import {
  Plus,
  FileText,
  FileAudio,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Play,
  Trash2,
  BookOpenCheck,
  RotateCcw,
  Info,
  X,
} from "lucide-react"
import { useState, useRef, useEffect, useMemo } from "react"
import {
  getSignedUploadUrl,
  createSourceFromGeminiFile,
  createSessionAndTrigger,
  createReportJob,
  deleteSourceItem,
  retrySourceItem,
} from "../actions"
import { createClient } from "@/utils/supabase/client"
import { RealtimePostgresChangesPayload } from "@supabase/supabase-js"
import ReportViewerModal from "./ReportViewerModal"

type ProcessingStats = {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
}

type SourceItem = {
  id: string
  type: 'pdf' | 'audio'
  title: string
  status: string
  createdAt: string
  stats?: ProcessingStats
  selected?: boolean
}

type Notice = {
  type: 'info' | 'success' | 'error'
  message: string
}

type LatestReportSummary = {
  sessionId: string
  createdAt: string
  evidenceCount: number
  warningCount: number
}

const READY_REPORT_STATUSES = new Set(['reasoning', 'completed'])

export default function SourcePanel({ subjectId }: { subjectId: string }) {
  const [items, setItems] = useState<SourceItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [viewingReportSessionId, setViewingReportSessionId] = useState<string | null>(null)
  const [latestReportSessionId, setLatestReportSessionId] = useState<string | null>(null)
  const [latestReport, setLatestReport] = useState<LatestReportSummary | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const supabase = createClient()

  const selectedAudios = useMemo(
    () => items.filter((item) => item.type === 'audio' && item.selected),
    [items],
  )

  const readyAudios = useMemo(
    () => selectedAudios.filter((item) => READY_REPORT_STATUSES.has(item.status)),
    [selectedAudios],
  )

  useEffect(() => {
    const countList = (value: unknown) => (Array.isArray(value) ? value.length : 0)

    const refreshLatestReportSession = async () => {
      const { data } = await supabase
        .from('session_reports')
        .select('session_id, created_at, report_json, sessions!inner(subject_id)')
        .eq('sessions.subject_id', subjectId)
        .order('created_at', { ascending: false })
        .limit(1)

      const latest = Array.isArray(data) && data.length > 0 ? data[0] : null
      const nextSessionId = latest?.session_id ?? null
      setLatestReportSessionId(nextSessionId)

      if (!latest) {
        setLatestReport(null)
        return
      }

      const payload = latest.report_json as Record<string, unknown> | null
      const evidenceCount =
        countList(payload?.professor_mentioned) +
        countList(payload?.likely) +
        countList(payload?.trap_warnings)
      const warningCount = countList(payload?.warnings)

      setLatestReport({
        sessionId: latest.session_id,
        createdAt: latest.created_at,
        evidenceCount,
        warningCount,
      })
    }

    const fetchInitialData = async () => {
      const [{ data: sources }, { data: sessions }] = await Promise.all([
        supabase.from('sources').select('*').eq('subject_id', subjectId).order('created_at', { ascending: false }),
        supabase.from('sessions').select('*').eq('subject_id', subjectId).order('created_at', { ascending: false }),
      ])

      const sessionIds = sessions?.map((s) => s.session_id) || []
      const chunksMap: Record<string, Array<{ session_id: string; status: string }>> = {}

      if (sessionIds.length > 0) {
        const { data: chunks } = await supabase
          .from('audio_chunks')
          .select('session_id, status')
          .in('session_id', sessionIds)

        chunks?.forEach((chunk) => {
          if (!chunksMap[chunk.session_id]) chunksMap[chunk.session_id] = []
          chunksMap[chunk.session_id].push(chunk)
        })
      }

      const combined: SourceItem[] = []

      sources?.forEach((source) => {
        combined.push({
          id: source.source_id,
          type: 'pdf',
          title: source.title,
          status: source.ingest_status,
          createdAt: source.created_at,
        })
      })

      sessions?.forEach((session) => {
        const chunkList = chunksMap[session.session_id] || []
        const stats = {
          total: chunkList.length,
          pending: chunkList.filter((chunk) => chunk.status === 'pending').length,
          processing: chunkList.filter((chunk) => chunk.status === 'processing').length,
          completed: chunkList.filter((chunk) => chunk.status === 'completed').length,
          failed: chunkList.filter((chunk) => chunk.status === 'failed').length,
        }

        combined.push({
          id: session.session_id,
          type: 'audio',
          title: session.gcs_audio_url.split('/').pop() || 'Audio',
          status: session.status,
          createdAt: session.created_at,
          stats,
        })
      })

      combined.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      setItems(combined)
      await refreshLatestReportSession()
    }

    fetchInitialData()

    const channel = supabase
      .channel('dashboard-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sources', filter: `subject_id=eq.${subjectId}` }, (payload) =>
        handleSourceChange(payload),
      )
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sessions', filter: `subject_id=eq.${subjectId}` }, (payload) =>
        handleSessionChange(payload),
      )
      .on('postgres_changes', { event: '*', schema: 'public', table: 'audio_chunks' }, (payload) => handleChunkChange(payload))
      .on('postgres_changes', { event: '*', schema: 'public', table: 'session_reports' }, async () => {
        await refreshLatestReportSession()
      })
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          console.log('Ready to receive realtime updates')
        }
      })

    return () => {
      supabase.removeChannel(channel)
    }
  }, [subjectId])

  const getStatusText = (status: string) => {
    switch (status) {
      case 'queued':
        return '대기 중'
      case 'pending':
        return '준비 중'
      case 'processing':
        return '처리 중...'
      case 'completed':
        return '완료됨'
      case 'reasoning':
        return '준비 완료'
      case 'succeeded':
        return '완료됨'
      case 'failed':
        return '실패'
      default:
        return status
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'succeeded':
      case 'reasoning':
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'queued':
        return <div className="h-2 w-2 rounded-full bg-gray-300" />
      default:
        return <Loader2 className="h-4 w-4 animate-spin text-primary" />
    }
  }

  const formatTimestamp = (raw: string) => {
    const date = new Date(raw)
    if (Number.isNaN(date.getTime())) return '-'
    return date.toLocaleString('ko-KR', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const fetchSessionStats = async (sessionId: string) => {
    const { data } = await supabase.from('audio_chunks').select('status').eq('session_id', sessionId)
    if (!data) return { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 }

    return {
      total: data.length,
      pending: data.filter((chunk) => chunk.status === 'pending').length,
      processing: data.filter((chunk) => chunk.status === 'processing').length,
      completed: data.filter((chunk) => chunk.status === 'completed').length,
      failed: data.filter((chunk) => chunk.status === 'failed').length,
    }
  }

  const handleSourceChange = (payload: RealtimePostgresChangesPayload<any>) => {
    if (payload.eventType === 'INSERT') {
      const newRow = payload.new
      setItems((prev) => [
        {
          id: newRow.source_id,
          type: 'pdf',
          title: newRow.title,
          status: newRow.ingest_status,
          createdAt: newRow.created_at,
        },
        ...prev,
      ])
      return
    }

    if (payload.eventType === 'UPDATE') {
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === payload.new.source_id) {
            return { ...item, status: payload.new.ingest_status }
          }
          return item
        }),
      )
      return
    }

    if (payload.eventType === 'DELETE') {
      setItems((prev) => prev.filter((item) => item.id !== payload.old.source_id))
    }
  }

  const handleSessionChange = (payload: RealtimePostgresChangesPayload<any>) => {
    const row = payload.new || payload.old

    if (payload.eventType === 'INSERT') {
      setItems((prev) => [
        {
          id: row.session_id,
          type: 'audio',
          title: row.gcs_audio_url.split('/').pop() || 'Audio',
          status: row.status,
          createdAt: row.created_at,
          stats: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        },
        ...prev,
      ])
      return
    }

    if (payload.eventType === 'UPDATE') {
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === row.session_id) {
            return { ...item, status: row.status }
          }
          return item
        }),
      )
      return
    }

    if (payload.eventType === 'DELETE') {
      setItems((prev) => prev.filter((item) => item.id !== row.session_id))
    }
  }

  const handleChunkChange = (payload: RealtimePostgresChangesPayload<any>) => {
    const row = payload.new || payload.old
    if (!row?.session_id) return

    const sessionId = row.session_id

    setItems((prev) => {
      const hasTarget = prev.some((item) => item.id === sessionId)
      if (!hasTarget) return prev

      fetchSessionStats(sessionId).then((nextStats) => {
        setItems((current) =>
          current.map((item) => {
            if (item.id === sessionId) {
              return { ...item, stats: nextStats }
            }
            return item
          }),
        )
      })

      return prev
    })
  }

  const handleDelete = async (id: string, type: 'pdf' | 'audio') => {
    if (!confirm('정말 이 항목을 삭제하시겠습니까?')) return

    setItems((prev) => prev.filter((item) => item.id !== id))

    try {
      await deleteSourceItem(id, type)
      setNotice({ type: 'success', message: '항목을 삭제했습니다.' })
    } catch {
      setNotice({ type: 'error', message: '삭제 중 오류가 발생했습니다.' })
    }
  }

  const handleRetry = async (id: string, type: 'pdf' | 'audio') => {
    if (!confirm('실패한 작업을 다시 실행할까요?')) return

    setItems((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          return { ...item, status: 'queued' }
        }
        return item
      }),
    )

    try {
      await retrySourceItem(id, type)
      setNotice({ type: 'success', message: '재실행을 시작했습니다.' })
    } catch {
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            return { ...item, status: 'failed' }
          }
          return item
        }),
      )
      setNotice({ type: 'error', message: '재실행 중 오류가 발생했습니다.' })
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setNotice(null)

    try {
      setIsUploading(true)
      let acceptedCount = 0

      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const isPdf = file.type === 'application/pdf'
        const isAudio = file.type.startsWith('audio/')

        if (!isPdf && !isAudio) continue

        acceptedCount += 1

        if (isAudio) {
          const fileName = `${subjectId}/${Date.now()}_${file.name}`
          const { url, gcsPath } = await getSignedUploadUrl({
            fileName,
            contentType: file.type,
          })

          const uploadResponse = await fetch(url, {
            method: 'PUT',
            body: file,
            headers: { 'Content-Type': file.type },
          })

          if (!uploadResponse.ok) {
            throw new Error('오디오 업로드에 실패했습니다.')
          }

          await createSessionAndTrigger(subjectId, file.name, gcsPath)
          continue
        }

        const sessionRes = await fetch('/api/gemini/upload-session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fileName: file.name,
            mimeType: file.type,
            sizeBytes: file.size,
          }),
        })

        if (!sessionRes.ok) {
          const errorText = await sessionRes.text()
          throw new Error(errorText || 'Gemini 업로드 세션 생성 실패')
        }

        const { uploadUrl } = (await sessionRes.json()) as { uploadUrl: string }

        const uploadRes = await fetch(uploadUrl, {
          method: 'POST',
          headers: {
            'X-Goog-Upload-Command': 'upload, finalize',
            'X-Goog-Upload-Offset': '0',
            'Content-Type': file.type,
          },
          body: file,
        })

        if (!uploadRes.ok) {
          const errorText = await uploadRes.text()
          throw new Error(errorText || 'Gemini 파일 업로드 실패')
        }

        const uploadPayload = (await uploadRes.json()) as { file?: { uri?: string } }
        const geminiFileUri = uploadPayload.file?.uri

        if (!geminiFileUri) {
          throw new Error('Gemini 파일 URI를 받지 못했습니다.')
        }

        await createSourceFromGeminiFile(subjectId, file.name, geminiFileUri)
      }

      if (acceptedCount === 0) {
        setNotice({ type: 'info', message: 'PDF 또는 오디오 파일만 업로드할 수 있습니다.' })
      } else {
        setNotice({
          type: 'success',
          message: `${acceptedCount}개 파일 업로드 요청이 접수되었습니다. 처리 상태를 실시간으로 반영합니다.`,
        })
      }
    } catch (error) {
      console.error(error)
      const message = error instanceof Error ? error.message : '업로드 중 오류가 발생했습니다.'
      setNotice({ type: 'error', message })
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const toggleSelection = (id: string) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, selected: !item.selected } : item)))
  }

  const handleGenerateReport = async () => {
    if (selectedAudios.length === 0) {
      setNotice({ type: 'error', message: '분석할 오디오 세션을 선택해주세요.' })
      return
    }

    if (readyAudios.length === 0) {
      setNotice({ type: 'error', message: '선택한 세션이 아직 리포트 생성 가능 상태가 아닙니다.' })
      return
    }

    const skippedCount = selectedAudios.length - readyAudios.length

    try {
      setIsGenerating(true)
      await createReportJob(
        subjectId,
        readyAudios.map((item) => item.id),
      )

      setItems((prev) => prev.map((item) => ({ ...item, selected: false })))
      setNotice({
        type: 'success',
        message:
          skippedCount > 0
            ? `리포트 생성을 시작했습니다. 준비되지 않은 ${skippedCount}개 세션은 제외되었습니다.`
            : '리포트 생성을 시작했습니다. 처리 완료까지 잠시 기다려주세요.',
      })
    } catch (error) {
      console.error(error)
      const message = error instanceof Error ? error.message : '리포트 생성 실패'
      setNotice({ type: 'error', message })
    } finally {
      setIsGenerating(false)
    }
  }

  const noticeClass =
    notice?.type === 'error'
      ? 'border-red-400/40 bg-red-500/10 text-red-100'
      : notice?.type === 'success'
        ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-100'
        : 'border-blue-400/40 bg-blue-500/10 text-blue-100'

  return (
    <div className="flex h-full w-full flex-col bg-transparent">
      <input
        type="file"
        multiple
        ref={fileInputRef}
        onChange={handleFileSelect}
        className="hidden"
        accept="application/pdf,audio/*"
      />

      <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 bg-black/20 px-4">
        <h2 className="text-sm font-semibold text-foreground">Sources</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => latestReportSessionId && setViewingReportSessionId(latestReportSessionId)}
            disabled={!latestReportSessionId}
            className="flex items-center gap-1 rounded-md p-1.5 text-xs font-medium text-foreground/70 transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            title={latestReportSessionId ? 'Latest Integrated Report' : '아직 생성된 리포트가 없습니다'}
          >
            <BookOpenCheck className="h-4 w-4" />
            Report
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1 rounded-md p-1.5 text-xs font-medium text-foreground/70 transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            title="Add Source"
          >
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add
          </button>
        </div>
      </div>

      {latestReport ? (
        <div className="border-b border-white/10 bg-primary/10 px-4 py-2 text-[11px] text-primary-foreground">
          <div className="flex items-center justify-between gap-2">
            <p>
              최신 통합 리포트: {formatTimestamp(latestReport.createdAt)} · 근거 {latestReport.evidenceCount}개 · 경고 {latestReport.warningCount}개
            </p>
            <button
              onClick={() => setViewingReportSessionId(latestReport.sessionId)}
              className="shrink-0 rounded border border-primary-foreground/25 bg-primary/30 px-2 py-0.5 text-[10px] font-semibold text-primary-foreground transition hover:bg-primary/40"
            >
              열기
            </button>
          </div>
        </div>
      ) : (
        <div className="border-b border-white/10 bg-black/10 px-4 py-2 text-[11px] text-foreground/60">
          생성된 통합 리포트가 없습니다. 오디오 세션을 선택해 리포트를 생성하세요.
        </div>
      )}

      <div className="border-b border-white/10 bg-black/10 px-4 py-2 text-[11px] text-foreground/65">
        PDF는 클라이언트에서 Gemini로 직접 업로드되며 원문은 UI에서 열람할 수 없습니다.
      </div>
      <div className="border-b border-white/10 bg-black/10 px-4 py-2 text-[11px] text-foreground/65">
        리포트는 선택한 오디오 전체를 통합해 1개로 생성됩니다.
      </div>

      {notice && (
        <div className={`flex items-start gap-2 border-b px-4 py-2 text-xs ${noticeClass}`}>
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p className="flex-1">{notice.message}</p>
          <button onClick={() => setNotice(null)} className="rounded p-0.5 transition hover:bg-black/20" aria-label="닫기">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {selectedAudios.length > 0 && (
        <div className="animate-in slide-in-from-top-2 border-b border-primary/20 bg-primary/10 p-2">
          <p className="mb-2 text-center text-[11px] text-foreground/80">
            선택 {selectedAudios.length}개 · 리포트 생성 가능 {readyAudios.length}개
          </p>
          <button
            onClick={handleGenerateReport}
            disabled={isGenerating || readyAudios.length === 0}
            className="flex w-full items-center justify-center gap-2 rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Generate Report ({readyAudios.length})
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
            <p className="text-xs text-foreground/50">No sources yet. Use the + button to add PDFs or Audio.</p>
          </div>
        ) : (
          <div className="flex flex-col">
            {items.map((item) => {
              const progressPercent =
                item.type === 'audio' && item.stats && item.stats.total > 0
                  ? Math.round((item.stats.completed / item.stats.total) * 100)
                  : 0

              return (
                <div
                  key={item.id}
                  className={`group relative flex cursor-pointer flex-col border-b border-white/10 px-4 py-3 transition-colors hover:bg-white/5 ${item.selected ? 'bg-primary/10' : ''}`}
                  onClick={() => {
                    if (item.type === 'audio') toggleSelection(item.id)
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="pt-0.5 text-foreground/50">
                      {item.type === 'pdf' ? <FileText className="h-4 w-4 text-foreground/60" /> : <FileAudio className="h-4 w-4 text-primary" />}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="mb-0.5 flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-medium text-foreground transition-colors group-hover:text-primary" title={item.title}>
                          {item.title}
                        </p>
                        <span className="text-[10px] text-foreground/45">{formatTimestamp(item.createdAt)}</span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] ${item.status === 'processing' ? 'animate-pulse font-semibold text-primary' : 'text-foreground/55'}`}>
                          {getStatusText(item.status)}
                        </span>
                        {getStatusIcon(item.status)}
                        {item.type === 'audio' && (
                          <input
                            type="checkbox"
                            checked={!!item.selected}
                            onChange={(e) => {
                              e.stopPropagation()
                              toggleSelection(item.id)
                            }}
                            className="ml-auto h-3.5 w-3.5 rounded border-white/20 bg-transparent text-primary focus:ring-primary"
                          />
                        )}
                      </div>

                      <div className="absolute right-2 top-2 hidden items-center gap-1 rounded border border-white/10 bg-black/55 px-1 backdrop-blur group-hover:flex">
                        {item.status === 'failed' && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleRetry(item.id, item.type)
                            }}
                            className="rounded p-1 text-foreground/60 transition-colors hover:bg-white/10 hover:text-foreground"
                            title="실패 작업 재실행"
                          >
                            <RotateCcw className="h-3 w-3" />
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(item.id, item.type)
                          }}
                          className="rounded p-1 text-foreground/60 transition-colors hover:bg-red-500/20 hover:text-red-300"
                          title="항목 삭제"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>

                      {item.type === 'audio' && item.stats && item.status === 'processing' && (
                        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-white/10">
                          <div className="h-full bg-primary transition-all duration-500" style={{ width: `${progressPercent}%` }} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <ReportViewerModal
        isOpen={!!viewingReportSessionId}
        onClose={() => setViewingReportSessionId(null)}
        sessionId={viewingReportSessionId || ''}
        title={items.find((item) => item.id === viewingReportSessionId)?.title || 'Analysis Report'}
      />
    </div>
  )
}
