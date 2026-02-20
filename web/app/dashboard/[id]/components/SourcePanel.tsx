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
  createSourceAndTrigger,
  createSessionAndTrigger,
  createReportJob,
  deleteSourceItem,
  retrySourceItem,
} from "../actions"
import { createClient } from "@/utils/supabase/client"
import { RealtimePostgresChangesPayload } from "@supabase/supabase-js"
import ReportViewerModal from "./ReportViewerModal"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

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
  queueCount: number
  confirmedCount: number
  candidateCount: number
  evidenceCount: number
  warningCount: number
}

type PendingAction = {
  kind: 'delete' | 'retry'
  id: string
  itemType: 'pdf' | 'audio'
  title: string
}

type UploadProgressState = {
  totalFiles: number
  uploadedFiles: number
  bytesTotal: number
  bytesUploaded: number
  perFileUploadedBytes: Record<string, number>
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
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [isActionSubmitting, setIsActionSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<UploadProgressState | null>(null)

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
      const confirmedItems = Array.isArray(payload?.recommendation_queue_confirmed)
        ? (payload?.recommendation_queue_confirmed as Array<Record<string, unknown>>)
        : []
      const candidateItems = Array.isArray(payload?.recommendation_queue_candidates)
        ? (payload?.recommendation_queue_candidates as Array<Record<string, unknown>>)
        : []
      const legacyItems = Array.isArray(payload?.recommendation_queue)
        ? (payload?.recommendation_queue as Array<Record<string, unknown>>)
        : []
      const queueItems = confirmedItems.length > 0 || candidateItems.length > 0
        ? [...confirmedItems, ...candidateItems]
        : legacyItems

      const queueCount = queueItems.length
      const evidenceCount = queueItems.reduce((acc, item) => {
        return acc + countList(item?.proof_refs) + countList(item?.references)
      }, 0)
      const warningCount = countList(payload?.warnings)

      setLatestReport({
        sessionId: latest.session_id,
        createdAt: latest.created_at,
        queueCount,
        confirmedCount: confirmedItems.length,
        candidateCount: candidateItems.length,
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
          title: session.gcs_audio_url.split('/').pop() || '오디오 파일',
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
          title: row.gcs_audio_url.split('/').pop() || '오디오 파일',
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

  const requestDelete = (item: SourceItem) => {
    setPendingAction({
      kind: 'delete',
      id: item.id,
      itemType: item.type,
      title: item.title,
    })
  }

  const requestRetry = (item: SourceItem) => {
    setPendingAction({
      kind: 'retry',
      id: item.id,
      itemType: item.type,
      title: item.title,
    })
  }

  const handleConfirmAction = async () => {
    if (!pendingAction) return

    const { kind, id, itemType } = pendingAction
    setIsActionSubmitting(true)
    setNotice(null)

    try {
      if (kind === 'delete') {
        await deleteSourceItem(id, itemType)
        setItems((prev) => prev.filter((item) => item.id !== id))
        setNotice({ type: 'success', message: '항목을 삭제했습니다.' })
      } else {
        setItems((prev) =>
          prev.map((item) => {
            if (item.id === id) {
              return { ...item, status: 'queued' }
            }
            return item
          }),
        )

        await retrySourceItem(id, itemType)
        setNotice({ type: 'success', message: '재실행을 시작했습니다.' })
      }
    } catch {
      if (kind === 'retry') {
        setItems((prev) =>
          prev.map((item) => {
            if (item.id === id) {
              return { ...item, status: 'failed' }
            }
            return item
          }),
        )
      }

      setNotice({
        type: 'error',
        message: kind === 'delete' ? '삭제 중 오류가 발생했습니다.' : '재실행 중 오류가 발생했습니다.',
      })
    } finally {
      setIsActionSubmitting(false)
      setPendingAction(null)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setNotice(null)

    setIsUploading(true)
    const acceptedFiles: File[] = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const isPdf = file.type === 'application/pdf'
      const isAudio = file.type.startsWith('audio/')
      if (isPdf || isAudio) acceptedFiles.push(file)
    }

    if (acceptedFiles.length === 0) {
      setNotice({ type: 'info', message: 'PDF 또는 오디오 파일만 업로드할 수 있습니다.' })
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    const fileKeys = acceptedFiles.map((file, index) => `${index}:${file.name}:${file.size}:${file.lastModified}`)
    const bytesTotal = acceptedFiles.reduce((sum, file) => sum + file.size, 0)
    setUploadProgress({
      totalFiles: acceptedFiles.length,
      uploadedFiles: 0,
      bytesTotal,
      bytesUploaded: 0,
      perFileUploadedBytes: Object.fromEntries(fileKeys.map((key) => [key, 0])),
    })

    const uploadBySignedUrl = (url: string, file: File, fileKey: string) =>
      new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('PUT', url, true)
        xhr.setRequestHeader('Content-Type', file.type)

        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) return
          setUploadProgress((prev) => {
            if (!prev) return prev
            const nextPerFileUploadedBytes = {
              ...prev.perFileUploadedBytes,
              [fileKey]: Math.min(file.size, Math.floor(event.loaded)),
            }
            const nextBytesUploaded = Object.values(nextPerFileUploadedBytes).reduce((sum, value) => sum + value, 0)
            return {
              ...prev,
              bytesUploaded: Math.min(prev.bytesTotal, nextBytesUploaded),
              perFileUploadedBytes: nextPerFileUploadedBytes,
            }
          })
        }

        xhr.onerror = () => {
          reject(new Error(`${file.name}: 네트워크 오류로 업로드 실패`))
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            setUploadProgress((prev) => {
              if (!prev) return prev
              const nextPerFileUploadedBytes = {
                ...prev.perFileUploadedBytes,
                [fileKey]: file.size,
              }
              const nextBytesUploaded = Object.values(nextPerFileUploadedBytes).reduce((sum, value) => sum + value, 0)
              return {
                ...prev,
                uploadedFiles: Math.min(prev.totalFiles, prev.uploadedFiles + 1),
                bytesUploaded: Math.min(prev.bytesTotal, nextBytesUploaded),
                perFileUploadedBytes: nextPerFileUploadedBytes,
              }
            })
            resolve()
            return
          }
          reject(new Error(`${file.name}: 업로드 실패 (HTTP ${xhr.status})`))
        }

        xhr.send(file)
      })

    const processSingleFile = async (file: File, fileKey: string) => {
      const isAudio = file.type.startsWith('audio/')
      const safeName = file.name.replace(/[^\w.\-()\[\]\s가-힣]/g, "_")
      const fileName = `${subjectId}/${Date.now()}_${crypto.randomUUID()}_${safeName}`
      const { url, gcsPath } = await getSignedUploadUrl({
        fileName,
        contentType: file.type,
      })

      await uploadBySignedUrl(url, file, fileKey)

      if (isAudio) {
        await createSessionAndTrigger(subjectId, file.name, gcsPath)
        return
      }

      await createSourceAndTrigger(subjectId, file.name, gcsPath)
    }

    type UploadResult = { fileName: string; ok: true } | { fileName: string; ok: false; error: string }
    const results: UploadResult[] = []
    const maxConcurrent = Math.min(3, acceptedFiles.length)
    let cursor = 0

    const workers = Array.from({ length: maxConcurrent }, async () => {
      while (true) {
        const index = cursor
        cursor += 1
        if (index >= acceptedFiles.length) return

        const file = acceptedFiles[index]
        const fileKey = fileKeys[index]
        try {
          await processSingleFile(file, fileKey)
          results.push({ fileName: file.name, ok: true })
        } catch (error) {
          console.error(error)
          const message = error instanceof Error ? error.message : '업로드 중 오류가 발생했습니다.'
          results.push({ fileName: file.name, ok: false, error: message })
        }
      }
    })

    try {
      await Promise.all(workers)
      const successCount = results.filter((r) => r.ok).length
      const failed = results.filter((r): r is Extract<UploadResult, { ok: false }> => !r.ok)

      if (failed.length === 0) {
        setNotice({
          type: 'success',
          message: `${successCount}개 파일 업로드 요청이 접수되었습니다. 처리 상태를 실시간으로 반영합니다.`,
        })
      } else {
        const failedNames = failed.slice(0, 2).map((r) => r.fileName).join(', ')
        const moreLabel = failed.length > 2 ? ` 외 ${failed.length - 2}개` : ''
        setNotice({
          type: successCount > 0 ? 'info' : 'error',
          message: `성공 ${successCount}개, 실패 ${failed.length}개 (${failedNames}${moreLabel})`,
        })
      }
    } finally {
      setIsUploading(false)
      setUploadProgress(null)
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

  const uploadPercent =
    uploadProgress && uploadProgress.bytesTotal > 0
      ? Math.min(100, Math.round((uploadProgress.bytesUploaded / uploadProgress.bytesTotal) * 100))
      : 0

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
        <h2 className="text-sm font-semibold text-foreground">자료</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => latestReportSessionId && setViewingReportSessionId(latestReportSessionId)}
            disabled={!latestReportSessionId}
            className="flex items-center gap-1 rounded-md p-1.5 text-xs font-medium text-foreground/70 transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            title={latestReportSessionId ? '최신 통합 리포트 보기' : '아직 생성된 리포트가 없습니다'}
          >
            <BookOpenCheck className="h-4 w-4" />
            리포트
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1 rounded-md p-1.5 text-xs font-medium text-foreground/70 transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            title="자료 업로드"
          >
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            업로드
          </button>
        </div>
      </div>

      {latestReport ? (
        <div className="border-b border-white/10 bg-primary/10 px-4 py-2 text-[11px] text-primary-foreground">
          <div className="flex items-center justify-between gap-2">
            <p>
              최신 통합 리포트: {formatTimestamp(latestReport.createdAt)} · 확정 {latestReport.confirmedCount}개 · 후보 {latestReport.candidateCount}개 · 총 {latestReport.queueCount}개 · 근거 {latestReport.evidenceCount}개 · 경고 {latestReport.warningCount}개
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
        PDF/오디오는 GCS 업로드 후 서버 파이프라인으로 처리됩니다. 원문은 UI에서 열람할 수 없습니다.
      </div>
      <div className="border-b border-white/10 bg-black/10 px-4 py-2 text-[11px] text-foreground/65">
        리포트는 선택한 오디오 전체를 통합해 1개로 생성됩니다.
      </div>

      {isUploading && uploadProgress && (
        <div className="border-b border-white/10 bg-blue-500/10 px-4 py-2">
          <div className="mb-1 flex items-center justify-between text-[11px] text-blue-100">
            <span>
              업로드 진행 중 ({uploadProgress.uploadedFiles}/{uploadProgress.totalFiles} 파일)
            </span>
            <span>{uploadPercent}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/15">
            <div
              className="h-full bg-blue-400 transition-all duration-200"
              style={{ width: `${uploadPercent}%` }}
            />
          </div>
          {uploadPercent === 100 && (
            <p className="mt-1 text-[10px] text-blue-100/90">
              업로드 완료, 서버 처리 시작 중...
            </p>
          )}
        </div>
      )}

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
            리포트 생성 ({readyAudios.length})
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
            <p className="text-xs text-foreground/50">아직 업로드된 자료가 없습니다. 우측 상단 업로드 버튼으로 PDF/오디오를 추가하세요.</p>
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
                              requestRetry(item)
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
                            requestDelete(item)
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
        title={items.find((item) => item.id === viewingReportSessionId)?.title || '분석 리포트'}
      />

      <Dialog open={!!pendingAction} onOpenChange={(open) => !open && setPendingAction(null)}>
        <DialogContent className="max-w-sm border-white/15 bg-[#101722] text-foreground">
          <DialogHeader>
            <DialogTitle>{pendingAction?.kind === 'delete' ? '항목 삭제' : '작업 재실행'}</DialogTitle>
            <DialogDescription className="text-foreground/70">
              {pendingAction?.kind === 'delete'
                ? `"${pendingAction?.title}" 항목을 삭제합니다. 이 작업은 되돌릴 수 없습니다.`
                : `"${pendingAction?.title}" 실패 작업을 다시 실행합니다.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:space-x-0">
            <button
              type="button"
              onClick={() => setPendingAction(null)}
              className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm font-medium text-foreground transition hover:bg-white/10"
              disabled={isActionSubmitting}
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleConfirmAction}
              className={`rounded-lg px-3 py-2 text-sm font-semibold text-white transition ${
                pendingAction?.kind === 'delete'
                  ? 'bg-red-500/90 hover:bg-red-500'
                  : 'bg-primary/90 text-primary-foreground hover:bg-primary'
              } disabled:opacity-60`}
              disabled={isActionSubmitting}
            >
              {isActionSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : pendingAction?.kind === 'delete' ? '삭제' : '재실행'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
