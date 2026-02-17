'use client'

import { Trash2, Save, Sliders } from "lucide-react"

export default function SettingsPanel() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 bg-black/20 p-4">
        <h2 className="text-sm font-semibold text-foreground">설정</h2>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-4">
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Sliders className="h-4 w-4 text-primary" />
            모델 설정
          </h3>
          <div className="mt-3 space-y-3">
            <div>
              <label className="block text-xs font-medium text-foreground/80">답변 스타일</label>
              <select className="mt-1 block w-full rounded-lg border border-white/15 bg-white/5 p-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option>균형 잡힘</option>
                <option>창의적임</option>
                <option>정확함</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/80">언어</label>
              <select className="mt-1 block w-full rounded-lg border border-white/15 bg-white/5 p-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option>한국어</option>
                <option>English</option>
              </select>
            </div>
          </div>
        </section>

        <div className="h-px bg-white/10" />

        <section>
          <h3 className="text-sm font-medium text-red-300">위험 구역</h3>
          <p className="mt-1 text-xs text-foreground/60">이 작업은 되돌릴 수 없습니다.</p>
          <div className="mt-3">
            <button className="flex w-full items-center justify-center gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-200 transition hover:bg-red-500/20">
              <Trash2 className="h-4 w-4" />
              과목 삭제
            </button>
          </div>
        </section>
      </div>

      <div className="border-t border-white/10 bg-black/20 p-4">
        <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:opacity-90">
          <Save className="h-4 w-4" />
          변경사항 저장
        </button>
      </div>
    </div>
  )
}
