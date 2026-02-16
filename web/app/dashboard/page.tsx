import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"
import Link from "next/link"
import { BookOpen } from "lucide-react"
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
    <div className="mobile-shell space-y-4 py-4">
      <section className="surface p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold">내 학습 프로젝트</h1>
            <p className="text-xs text-muted-foreground">과목별로 출제 신호 분석 세션을 관리하세요.</p>
          </div>
          <div className="shrink-0">
            <AddSubjectModal buttonOnly />
          </div>
        </div>
      </section>

      {subjects && subjects.length > 0 ? (
        <section className="space-y-3">
          {subjects.map((subject) => (
            <Link key={subject.subject_id} href={`/dashboard/${subject.subject_id}`} className="surface block p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-base font-semibold">{subject.name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    생성일 {new Date(subject.created_at).toLocaleDateString('ko-KR')}
                  </p>
                </div>
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
            </Link>
          ))}
        </section>
      ) : (
        <section className="surface p-6 text-center">
          <BookOpen className="mx-auto h-8 w-8 text-primary" />
          <p className="mt-3 text-sm font-semibold">아직 과목이 없습니다.</p>
          <p className="mt-1 text-xs text-muted-foreground">과목을 추가하고 학습 내비게이션 분석을 시작하세요.</p>
          <div className="mt-4 inline-flex">
            <AddSubjectModal buttonOnly />
          </div>
        </section>
      )}
    </div>
  )
}
