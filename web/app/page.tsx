import Link from "next/link"
import { ArrowRight, CheckCircle2, Compass, ShieldCheck, Sparkles } from "lucide-react"

const flow = [
  "강의 오디오 업로드",
  "교재 파일 업로드 (세션 한정 처리)",
  "출제 신호 + 구조 매칭 분석",
  "학습 우선순위 카드 확인",
]

const principles = [
  "교재 원문 장문 제공/재현 차단",
  "근거 위치(anchor/page/timecode) 중심 안내",
  "교재 대체가 아닌 학습 방향 최적화",
]

export default function LandingPage() {
  return (
    <main className="pb-10 pt-6">
      <div className="mobile-shell space-y-5">
        <section className="surface p-5">
          <p className="inline-flex items-center gap-1 rounded-full bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground">
            <Sparkles className="h-3.5 w-3.5" />
            학습 내비게이션 엔진
          </p>
          <h1 className="mt-3 text-2xl font-bold leading-tight">
            교재를 대체하지 않고, <br />
            <span className="text-primary">시험 대비 우선순위</span>만 정확히 안내합니다.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Thunder Navigator는 학기 전체 강의 맥락에서 교수의 출제 신호를 찾아 교재의 어느 위치를 먼저 학습해야 하는지
            알려줍니다.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-2">
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
            >
              지금 시작하기
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center rounded-xl border border-border bg-card px-4 py-3 text-sm font-semibold"
            >
              대시보드 보기
            </Link>
          </div>
        </section>

        <section className="surface p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Compass className="h-4 w-4 text-primary" />
            사용 흐름
          </h2>
          <ul className="mt-3 space-y-2 text-sm">
            {flow.map((item, index) => (
              <li key={item} className="flex items-start gap-2">
                <span className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
                  {index + 1}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="surface p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            저작권 안전 설계
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {principles.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
