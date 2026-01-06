'use client'

import { Plus, FileText, Upload, MoreVertical, FileAudio } from "lucide-react"
import { useState } from "react"

export default function SourcePanel({ subjectId }: { subjectId: string }) {
  const [sources, setSources] = useState<any[]>([]) // 나중에 DB 연동

  return (
    <div className="flex h-full flex-col border-r border-gray-200 bg-white w-80">
      <div className="flex items-center justify-between border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900">소스</h2>
        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
          {sources.length}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {sources.length === 0 ? (
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
            {/* 소스 목록 아이템 예시 */}
          </div>
        )}
      </div>

      <div className="border-t border-gray-200 p-4">
        <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          <Plus className="h-5 w-5" />
          소스 추가
        </button>
      </div>
    </div>
  )
}
