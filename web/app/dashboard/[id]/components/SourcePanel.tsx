'use client'

import { Plus, FileText, Upload, MoreVertical, FileAudio, CheckCircle2, AlertCircle, Loader2, Play, Trash2, BookOpenCheck } from "lucide-react"
import { useState, useRef, useEffect, useMemo } from "react"
import { getSignedUploadUrl, createSourceAndTrigger, createSessionAndTrigger, createReportJob, deleteSourceItem } from "../actions"
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
    status: string // sources.ingest_status OR sessions.status
    createdAt: string
    stats?: ProcessingStats // For audio
    selected?: boolean // For checkbox
    logs?: { ts: string, msg: string }[] // Debug logs
}

export default function SourcePanel({ subjectId }: { subjectId: string }) {
  const [items, setItems] = useState<SourceItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [viewingReportSessionId, setViewingReportSessionId] = useState<string | null>(null)
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const supabase = createClient()

  // Initial Fetch & Realtime Subscription
  useEffect(() => {
    const fetchInitialData = async () => {
        // 1. Fetch PDFs (sources)
        const { data: sources } = await supabase
            .from('sources')
            .select('*')
            .eq('subject_id', subjectId)
            .order('created_at', { ascending: false })
            
        // 2. Fetch Audios (sessions) with aggregated stats manually (join is tricky for stats)
        // Let's fetch sessions first
        const { data: sessions } = await supabase
            .from('sessions')
            .select('*')
            .eq('subject_id', subjectId)
            .order('created_at', { ascending: false })

        // 3. Fetch all chunks for these sessions for stats
        const sessionIds = sessions?.map(s => s.session_id) || []
        let chunksMap: Record<string, any[]> = {}
        
        if (sessionIds.length > 0) {
            const { data: chunks } = await supabase
                .from('audio_chunks')
                .select('session_id, status')
                .in('session_id', sessionIds)
            
            chunks?.forEach(c => {
                if (!chunksMap[c.session_id]) chunksMap[c.session_id] = []
                chunksMap[c.session_id].push(c)
            })
        }

        // Merge into items
        const combined: SourceItem[] = []
        
        sources?.forEach(s => {
            combined.push({
                id: s.source_id,
                type: 'pdf',
                title: s.title,
                status: s.ingest_status,
                createdAt: s.created_at
            })
        })

        sessions?.forEach(s => {
            const cList = chunksMap[s.session_id] || []
            const stats = {
                total: cList.length,
                pending: cList.filter(c => c.status === 'pending').length,
                processing: cList.filter(c => c.status === 'processing').length,
                completed: cList.filter(c => c.status === 'completed').length,
                failed: cList.filter(c => c.status === 'failed').length,
            }

            combined.push({
                id: s.session_id,
                type: 'audio',
                title: s.gcs_audio_url.split('/').pop() || 'Audio', // approximate title
                status: s.status,
                createdAt: s.created_at,
                stats,
                logs: s.logs // Debug logs
            })
        })

        // Sort by created most recent
        combined.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        setItems(combined)
    }

    fetchInitialData()

    // Subscribe to changes
    const channel = supabase.channel('dashboard-realtime')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'sources', filter: `subject_id=eq.${subjectId}` }, 
            (payload) => handleSourceChange(payload))
        .on('postgres_changes', { event: '*', schema: 'public', table: 'sessions', filter: `subject_id=eq.${subjectId}` }, 
            (payload) => handleSessionChange(payload))
        .on('postgres_changes', { event: '*', schema: 'public', table: 'audio_chunks' }, 
            (payload) => handleChunkChange(payload)) 
        .subscribe((status) => {
            if (status === 'SUBSCRIBED') {
                console.log('Ready to receive realtime updates');
            }
        })

    return () => { supabase.removeChannel(channel) }
  }, [subjectId])

  // Helper for status text
  const getStatusText = (status: string) => {
    switch (status) {
        case 'queued': return '대기 중';
        case 'pending': return '준비 중';
        case 'processing': return '처리 중...';
        case 'completed': return '완료됨';
        case 'reasoning': return '준비 완료'; 
        case 'succeeded': return '완료됨';
        case 'failed': return '실패';
        default: return status;
    }
  }

  // Handlers for Realtime
  const handleSourceChange = (payload: RealtimePostgresChangesPayload<any>) => {
      if (payload.eventType === 'INSERT') {
          const newRow = payload.new
          setItems(prev => [{
              id: newRow.source_id,
              type: 'pdf',
              title: newRow.title,
              status: newRow.ingest_status,
              createdAt: newRow.created_at
          }, ...prev])
      } else if (payload.eventType === 'UPDATE') {
          setItems(prev => prev.map(item => {
              if (item.id === payload.new.source_id) {
                  return { ...item, status: payload.new.ingest_status }
              }
              return item
          }))
      }
  }

  const handleSessionChange = (payload: RealtimePostgresChangesPayload<any>) => {
      const newRow = payload.new
      if (payload.eventType === 'INSERT') {
          setItems(prev => [{
              id: newRow.session_id,
              type: 'audio',
              title: newRow.gcs_audio_url.split('/').pop() || 'Audio',
              status: newRow.status,
              createdAt: newRow.created_at,
              stats: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
              logs: newRow.logs
          }, ...prev])
      } else if (payload.eventType === 'UPDATE') {
          setItems(prev => prev.map(item => {
              if (item.id === newRow.session_id) {
                  return { ...item, status: newRow.status, logs: newRow.logs }
              }
              return item
          }))
      }
  }

  const handleChunkChange = (payload: RealtimePostgresChangesPayload<any>) => {
      // payload.new has session_id. Find if it is in our items.
      const row = payload.new || payload.old
      const sessionId = row.session_id
      
      setItems(prev => {
          const targetIndex = prev.findIndex(p => p.id === sessionId)
          if (targetIndex === -1) return prev // Not our session

          // Fetch stats for this session
          fetchSessionStats(sessionId).then(newStats => {
              setItems(current => current.map(item => {
                  // Update stats AND derived status if needed
                  if (item.id === sessionId) {
                     // If stats show activity, ensure item status reflects it (optional UI enhancement)
                     return { ...item, stats: newStats }
                  }
                  return item
              }))
          })
          
          return prev
      })
  }

  const handleDelete = async (id: string, type: 'pdf' | 'audio') => {
      if (!confirm("정말 이 항목을 삭제하시겠습니까?")) return
      
      // Optimistic update
      setItems(prev => prev.filter(i => i.id !== id))
      
      try {
          await deleteSourceItem(id, type)
      } catch (e) {
          alert("삭제 중 오류가 발생했습니다.")
          // Rollback if needed (simplified here)
      }
  }
  
  const fetchSessionStats = async (sessionId: string) => {
      const { data } = await supabase.from('audio_chunks').select('status').eq('session_id', sessionId)
      if (!data) return { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 }
      return {
          total: data.length,
          pending: data.filter(c => c.status === 'pending').length,
          processing: data.filter(c => c.status === 'processing').length,
          completed: data.filter(c => c.status === 'completed').length,
          failed: data.filter(c => c.status === 'failed').length,
      }
  }


  // Actions
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    try {
        setIsUploading(true)
        for (let i = 0; i < files.length; i++) {
            const file = files[i]
            const isPdf = file.type === 'application/pdf';
            const isAudio = file.type.startsWith('audio/');
            
            if (!isPdf && !isAudio) continue 

            const fileName = `${subjectId}/${Date.now()}_${file.name}`
            const { url, gcsPath } = await getSignedUploadUrl({ 
                fileName, 
                contentType: file.type 
            })

            await fetch(url, {
                method: 'PUT',
                body: file,
                headers: { 'Content-Type': file.type }
            })

            if (isAudio) {
               await createSessionAndTrigger(subjectId, file.name, gcsPath)
            } else {
               await createSourceAndTrigger(subjectId, file.name, gcsPath)
            }
        }
    } catch (error) {
        console.error(error)
        alert("업로드 중 오류가 발생했습니다.")
    } finally {
        setIsUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const toggleSelection = (id: string) => {
      setItems(prev => prev.map(item => item.id === id ? { ...item, selected: !item.selected } : item))
  }

  const handleGenerateReport = async () => {
      const selectedIds = items.filter(i => i.type === 'audio' && i.selected).map(i => i.id)
      if (selectedIds.length === 0) return alert("분석할 오디오 세션을 선택해주세요.")
      
      try {
          setIsGenerating(true)
          await createReportJob(subjectId, selectedIds)
          alert("리포트 생성이 시작되었습니다! (Phase 3/4)")
          // Clear selections
          setItems(prev => prev.map(i => ({ ...i, selected: false })))
      } catch (e) {
          console.error(e)
          alert("리포트 생성 실패")
      } finally {
          setIsGenerating(false)
      }
  }

  // --- Render Helpers ---

  const getStatusIcon = (status: string) => {
      switch (status) { // Normalize status
          case 'succeeded':
          case 'reasoning': // Treat reasoning as completed for icon
          case 'completed': return <CheckCircle2 className="h-4 w-4 text-green-500" />
          case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />
          case 'queued': return <div className="h-2 w-2 rounded-full bg-gray-300" />
          default: return <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
      }
  }

  const renderProgressBar = (stats: ProcessingStats) => {
      if (stats.total === 0) return null
      const percent = Math.round((stats.completed / stats.total) * 100)
      return (
          <div className="mt-1 w-full">
            <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
                <span>{percent}% ({stats.completed}/{stats.total})</span>
                {stats.failed > 0 && <span className="text-red-500">{stats.failed} failed</span>}
            </div>
            <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                <div 
                    className={`h-full rounded-full transition-all duration-500 ${stats.failed > 0 ? 'bg-orange-400' : 'bg-green-500'}`}
                    style={{ width: `${percent}%` }} 
                />
            </div>
          </div>
      )
  }

  const renderBadge = (item: SourceItem) => {
      // PDF
      if (item.type === 'pdf') {
          return (
            <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                item.status === 'succeeded' ? 'bg-green-50 text-green-700 ring-green-600/20' :
                item.status === 'failed' ? 'bg-red-50 text-red-700 ring-red-600/20' :
                'bg-yellow-50 text-yellow-800 ring-yellow-600/20'
            }`}>
              {item.status === 'succeeded' ? 'Ready' : item.status}
            </span>
          )
      }
      // Audio
      return (
        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
            item.status === 'completed' ? 'bg-blue-50 text-blue-700 ring-blue-700/10' :
            item.status === 'reasoning' ? 'bg-green-50 text-green-700 ring-green-600/20' :
            item.status === 'failed' ? 'bg-red-50 text-red-700 ring-red-600/20' :
            'bg-gray-50 text-gray-600 ring-gray-500/10'
        }`}>
          {item.status === 'reasoning' ? 'Ready' : item.status}
        </span>
      )
  }

  return (
    <div className="flex h-full flex-col border-r border-gray-200 bg-white w-80">
      <input 
        type="file" 
        multiple
        ref={fileInputRef} 
        onChange={handleFileSelect} 
        className="hidden" 
        accept="application/pdf,audio/*" 
      />

      <div className="flex items-center justify-between border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900">소스</h2>
        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
          {items.length}
        </span>
      </div>

      {/* Action Bar for Report Generation */}
      {items.some(i => i.type === 'audio' && i.selected) && (
          <div className="bg-indigo-50 p-2 border-b border-indigo-100 animate-in slide-in-from-top-2">
              <button 
                onClick={handleGenerateReport}
                disabled={isGenerating}
                className="w-full flex items-center justify-center gap-2 rounded bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-indigo-500"
              >
                  {isGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                  리포트 생성 ({items.filter(i => i.selected).length})
              </button>
          </div>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="rounded-full bg-gray-50 p-3">
              <Upload className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-2 text-sm text-gray-500">
              PDF나 오디오 파일을<br />추가해주세요
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
                <div key={item.id} className="relative flex flex-col rounded-lg border border-gray-200 p-3 hover:border-indigo-300 transition-colors bg-white">
                    <div className="flex items-start gap-3">
                        {/* Checkbox for Audio only */}
                        {item.type === 'audio' ? (
                            <div className="pt-0.5">
                                <input 
                                    type="checkbox" 
                                    checked={!!item.selected}
                                    onChange={() => toggleSelection(item.id)}
                                    className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                                />
                            </div>
                        ) : (
                            <div className="pt-0.5">
                                <FileText className="h-4 w-4 text-orange-500" />
                            </div>
                        )}
                        
                        <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-start mb-1">
                                <p className="text-sm font-medium text-gray-900 truncate" title={item.title}>
                                    {item.title}
                                </p>
                                {/* Status Icon & Text */}
                                <div className="flex items-center gap-2">
                                    <span className={`text-[10px] ${item.status === 'processing' ? 'text-indigo-600 animate-pulse font-semibold' : 'text-gray-400'}`}>
                                        {getStatusText(item.status)}
                                    </span>
                                    {getStatusIcon(item.status)}
                                </div>
                            </div>
                            
                            <div className="flex items-center gap-2 mb-1">
                                {renderBadge(item)}
                                <span className="text-[10px] text-gray-400">
                                    {new Date(item.createdAt).toLocaleTimeString()}
                                </span>
                                
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleDelete(item.id, item.type); }}
                                    className="ml-auto p-1 hover:bg-gray-200 rounded text-gray-400 hover:text-red-500 transition-colors"
                                    title="항목 삭제"
                                >
                                    <Trash2 className="h-3 w-3" />
                                </button>
                            </div>

                            {/* Report View Button for Completed Audio */}
                            {item.type === 'audio' && item.status === 'completed' && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setViewingReportSessionId(item.id); }}
                                    className="mt-2 w-full flex items-center justify-center gap-1.5 rounded-md bg-indigo-50 px-2 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition border border-indigo-200 mb-1"
                                >
                                    <BookOpenCheck className="h-3.5 w-3.5" />
                                    분석 리포트 보기
                                </button>
                            )}

                            {/* Audio Specific Progress - Show only when processing short-circuit */}
                            {item.type === 'audio' && item.stats && item.status !== 'completed' && item.status !== 'reasoning' && item.status !== 'succeeded' && (
                                <div className="mt-2 bg-gray-50 p-2 rounded text-xs text-gray-600">
                                    <div className="flex justify-between border-b pb-1 mb-1 border-gray-200">
                                        <span>Phase 2 (Signal)</span>
                                    </div>
                                    {renderProgressBar(item.stats)}
                                </div>
                            )}

                            {/* Reasoning Phase Logs */}
                            {item.type === 'audio' && item.logs && item.logs.length > 0 && (
                                <div className="mt-2 bg-slate-900 text-emerald-400 p-2.5 rounded shadow-inner text-[10px] font-mono leading-relaxed">
                                    <div className="flex items-center justify-between border-b border-slate-700 pb-1 mb-1.5 opacity-80">
                                        <span className="font-semibold uppercase tracking-wider text-[9px]">Phase 4 Logs</span>
                                        <span className="text-[9px] text-slate-400">{item.status}</span>
                                    </div>
                                    <div className="flex flex-col gap-1 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                                        {[...item.logs].reverse().map((log, i) => (
                                            <div key={i} className="break-words border-l-2 border-slate-700 pl-2">
                                                <span className="text-slate-500 text-[9px] block mb-0.5">
                                                    {log.ts && log.ts.includes('T') ? log.ts.split('T')[1].split('.')[0] : ''}
                                                </span>
                                                {log.msg}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-gray-200 p-4">
        <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:bg-gray-400"
        >
          {isUploading ? (
              <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  업로드 중...
              </span>
          ) : (
              <>
                <Plus className="h-5 w-5" />
                소스 추가
              </>
          )}
        </button>
      </div>

      <ReportViewerModal 
        isOpen={!!viewingReportSessionId} 
        onClose={() => setViewingReportSessionId(null)}
        sessionId={viewingReportSessionId || ''}
        title={items.find(i => i.id === viewingReportSessionId)?.title || '분석 리포트'}
      />
    </div>
  )
}

