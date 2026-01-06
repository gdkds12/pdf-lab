import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"
import Link from "next/link"
import { Plus, Book, LogOut } from "lucide-react"
import AddSubjectModal from "./components/AddSubjectModal"
import { signout } from "../login/actions"

export default async function DashboardPage() {
  const supabase = await createClient()

  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const { data: subjects } = await supabase
    .from('subjects')
    .select('*')
    .order('created_at', { ascending: false })

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between">
            <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
                    <Book className="h-5 w-5 text-white" />
                </div>
                <span className="text-xl font-bold text-gray-900">Dashboard</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">{user.email}</span>
              <form action={signout}>
                <button
                    type="submit"
                    className="rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500"
                >
                    <LogOut className="h-5 w-5" />
                </button>
              </form>
            </div>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">내 과목</h1>
          <AddSubjectModal />
        </div>

        {subjects && subjects.length > 0 ? (
          <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map((subject) => (
              <Link
                href={`/dashboard/${subject.subject_id}`}
                key={subject.subject_id}
                className="group relative overflow-hidden rounded-xl bg-white p-6 shadow-sm ring-1 ring-gray-200 transition hover:shadow-md hover:ring-indigo-200 block"
              >
                <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                        <Book className="h-6 w-6" />
                    </div>
                </div>
                <h3 className="mt-4 text-lg font-semibold text-gray-900 ">
                  {subject.name}
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                   {new Date(subject.created_at).toLocaleDateString()} 생성됨
                </p>
                
                {/* 추후 상세 페이지 링크 연결 */}
                <div className="mt-4 flex gap-2">
                    <span className="inline-flex items-center rounded-md bg-gray-50 px-2 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10">
                        교재 0권
                    </span>
                    <span className="inline-flex items-center rounded-md bg-gray-50 px-2 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10">
                        분석 0건
                    </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="mt-10 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-300 bg-white p-12 text-center">
            <Book className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-semibold text-gray-900">과목이 없습니다</h3>
            <p className="mt-1 text-sm text-gray-500">새로운 과목을 추가하여 학습을 시작하세요.</p>
            <div className="mt-6">
              <AddSubjectModal buttonOnly />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
