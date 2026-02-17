import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"
import Link from "next/link"
import { BookOpen, CalendarDays, FolderOpenDot } from "lucide-react"
import AddSubjectModal from "./components/AddSubjectModal"

export default async function DashboardPage() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const { data: subjects } = await supabase.from('subjects').select('*').order('created_at', { ascending: false })

  return (
    <div className="th-shell space-y-5">
      <section className="th-card">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="th-pill mb-2 inline-flex">학습 워크스페이스</p>
            <h1 className="text-xl font-semibold tracking-tight">내 학습 프로젝트</h1>
            <p className="th-muted mt-1">과목별로 출제 신호 분석 세션을 관리하세요.</p>
          </div>
          <div className="shrink-0">
            <AddSubjectModal buttonOnly />
          </div>
        </div>
      </section>

      {subjects && subjects.length > 0 ? (
        <section className="grid gap-3 sm:grid-cols-2">
          {subjects.map((subject) => (
            <Link
              key={subject.subject_id}
              href={`/dashboard/${subject.subject_id}`}
              className="th-card block transition hover:-translate-y-0.5 hover:bg-white/10"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-base font-semibold tracking-tight">{subject.name}</p>
                  <p className="mt-2 inline-flex items-center gap-1 text-xs text-foreground/70">
                    <CalendarDays className="h-3.5 w-3.5" />
                    {new Date(subject.created_at).toLocaleDateString('ko-KR')}
                  </p>
                </div>
                <FolderOpenDot className="h-5 w-5 text-primary" />
              </div>
            </Link>
          ))}
        </section>
      ) : (
        <section className="th-card text-center">
          <BookOpen className="mx-auto h-8 w-8 text-primary" />
          <p className="mt-3 text-base font-semibold">아직 과목이 없습니다.</p>
          <p className="mt-1 text-sm text-foreground/70">과목을 추가하고 학습 내비게이션 분석을 시작하세요.</p>
          <div className="mt-4 inline-flex">
            <AddSubjectModal buttonOnly />
          </div>
        </section>
      )}
    </div>
  )
}
