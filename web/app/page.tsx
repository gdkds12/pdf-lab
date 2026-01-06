import Link from "next/link"
import { ArrowRight, BookOpen, Brain, Clock, GraduationCap } from 'lucide-react'
import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"

export default async function LandingPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (user) {
    redirect('/dashboard')
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-gray-100 bg-white/80 backdrop-blur-xl">
        <div className="container mx-auto flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <BookOpen className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight text-gray-900">Project Thunder</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm font-semibold text-gray-600 transition hover:text-gray-900"
            >
              Sign in
            </Link>
            <Link
              href="/login"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="relative overflow-hidden py-24 sm:py-32">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-6xl">
                시험 공부의 <span className="text-indigo-600">핵심</span>만<br />
                빠르게 파악하세요
              </h1>
              <p className="mt-6 text-lg leading-8 text-gray-600">
                강의 오디오와 전공 서적을 통합 분석하여,<br className="hidden sm:inline" />
                "시험에 나올 내용"만 정리된 리포트를 자동으로 생성해드립니다.
              </p>
              <div className="mt-10 flex items-center justify-center gap-x-6">
                <Link
                  href="/login"
                  className="rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-lg transition hover:bg-indigo-500 hover:shadow-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                >
                  무료로 시작하기
                </Link>
                <Link href="#features" className="group flex items-center gap-1 text-base font-semibold leading-7 text-gray-900">
                  더 알아보기 <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Section */}
        <section id="features" className="bg-gray-50 py-24 sm:py-32">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
                왜 Project Thunder인가요?
              </h2>
              <p className="mt-4 text-lg text-gray-600">
                Map-Reduce 아키텍처를 통해 전체 맥락을 파악하고 정확한 근거를 제시합니다.
              </p>
            </div>
            
            <div className="mx-auto mt-16 max-w-7xl sm:mt-20 lg:mt-24">
              <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-10 lg:max-w-none lg:grid-cols-3">
                {[
                  {
                    icon: GraduationCap,
                    title: "교수님 강조 포인트",
                    description: "강의 중 '시험에 나온다', '중요하다'고 말씀하신 부분을 놓치지 않고 포착합니다."
                  },
                  {
                    icon: Brain,
                    title: "명확한 교재 근거",
                    description: "오디오 신호에 해당하는 전공 서적의 정확한 페이지와 정의를 찾아 연결해드립니다."
                  },
                  {
                    icon: Clock,
                    title: "함정 문제 예방",
                    description: "교수님의 설명과 교재 정의가 달라 혼동하기 쉬운 '함정' 포인트를 미리 경고합니다."
                  }
                ].map((feature) => (
                  <div key={feature.title} className="relative rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200 transition hover:shadow-md">
                    <dt className="flex flex-col items-center gap-4 text-center">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                        <feature.icon className="h-6 w-6" />
                      </div>
                      <div className="text-lg font-semibold leading-7 text-gray-900">
                        {feature.title}
                      </div>
                    </dt>
                    <dd className="mt-2 text-center text-base leading-7 text-gray-600">
                      {feature.description}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-100 py-12">
        <div className="container mx-auto px-4 text-center text-sm text-gray-500">
          <p>&copy; {new Date().getFullYear()} Project Thunder. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
