'use client'

import { Trash2, Save, Sliders } from "lucide-react"

export default function SettingsPanel() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900">설정</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Model Configuration */}
        <div>
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <Sliders className="h-4 w-4" />
                모델 설정
            </h3>
            <div className="mt-3 space-y-3">
                <div>
                    <label className="block text-xs font-medium text-gray-700">답변 스타일</label>
                    <select className="mt-1 block w-full rounded-md border-gray-300 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                        <option>균형 잡힘</option>
                        <option>창의적임</option>
                        <option>정확함</option>
                    </select>
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-700">언어</label>
                    <select className="mt-1 block w-full rounded-md border-gray-300 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                        <option>한국어</option>
                        <option>English</option>
                    </select>
                </div>
            </div>
        </div>

        <hr className="border-gray-100" />

        {/* Danger Zone */}
        <div>
            <h3 className="text-sm font-medium text-red-600">위험 구역</h3>
            <p className="mt-1 text-xs text-gray-500">이 작업은 되돌릴 수 없습니다.</p>
            <div className="mt-3">
                <button className="flex w-full items-center justify-center gap-2 rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition border border-red-200">
                    <Trash2 className="h-4 w-4" />
                    과목 삭제
                </button>
            </div>
        </div>
      </div>
      
      <div className="border-t border-gray-200 p-4">
        <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-gray-800 transition">
            <Save className="h-4 w-4" />
            변경사항 저장
        </button>
      </div>
    </div>
  )
}
