'use client'

import { useState } from 'react'
import { Plus, X, Loader2 } from 'lucide-react'
import { addSubject } from '../actions'

export default function AddSubjectModal({ buttonOnly = false }: { buttonOnly?: boolean }) {
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (formData: FormData) => {
    setLoading(true)
    await addSubject(formData)
    setLoading(false)
    setIsOpen(false)
  }

  const triggerButton = (
    <button
      onClick={() => setIsOpen(true)}
      className="inline-flex items-center gap-x-2 rounded-md bg-indigo-600 px-3.5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
    >
      <Plus className="-ml-0.5 h-5 w-5" aria-hidden="true" />
      과목 추가
    </button>
  )

  if (buttonOnly && !isOpen) return triggerButton

  return (
    <>
      {!buttonOnly && triggerButton}

      {isOpen && (
        <div className="relative z-50" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />

          <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <div className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                <div className="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                    onClick={() => setIsOpen(false)}
                  >
                    <span className="sr-only">Close</span>
                    <X className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                
                <div className="sm:flex sm:items-start">
                  <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                    <h3 className="text-base font-semibold leading-6 text-gray-900" id="modal-title">
                      새 과목 추가
                    </h3>
                    <div className="mt-2 text-sm text-gray-500">
                        <p>관리할 과목의 이름을 입력해주세요.</p>
                    </div>
                    
                    <form action={handleSubmit} className="mt-5 sm:flex sm:items-center">
                        <div className="w-full sm:max-w-xs">
                            <label htmlFor="name" className="sr-only">Name</label>
                            <input
                                type="text"
                                name="name"
                                id="name"
                                required
                                className="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 pl-2"
                                placeholder="예: 전자기학"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="mt-3 inline-flex w-full items-center justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 sm:ml-3 sm:mt-0 sm:w-auto disabled:opacity-50"
                        >
                            {loading ? <Loader2 className="animate-spin h-5 w-5"/> : '추가하기'}
                        </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
