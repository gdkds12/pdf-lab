"use client"

import type React from "react"
import { useState } from "react"
import { ChevronDown } from "lucide-react"

const faqData = [
  {
    question: "Project Thunder는 어떤 서비스인가요?",
    answer:
      "Project Thunder는 AI 기술을 활용하여 대학생들의 시험 대비를 돕는 플랫폼입니다. 전공 서적과 강의 내용을 분석하여 핵심 요약, 예상 문제, 학습 가이드를 제공합니다.",
  },
  {
    question: "AI 시험 분석은 어떻게 동작하나요?",
    answer:
      "업로드하신 교재 PDF와 강의 녹음 파일을 심층 분석하여 중요 키워드와 출제 경향을 추출합니다. 최신 AI 모델(Gemini, GPT)이 교차 검증하여 신뢰도 높은 정보를 제공합니다.",
  },
  {
    question: "어떤 파일을 업로드할 수 있나요?",
    answer:
      "PDF 형식의 교재 및 논문, 그리고 MP3, M4A 등 대부분의 강의 녹음 파일 포맷을 지원합니다. 업로드 즉시 분석이 시작됩니다.",
  },
  {
    question: "무료로 사용할 수 있나요?",
    answer:
      "네, 기본적인 자료 분석과 챗봇 질문 기능은 무료로 제공됩니다. 더 심도 있는 분석과 무제한 기능을 원하시면 유료 플랜을 이용하실 수 있습니다.",
  },
  {
    question: "예상 문제의 적중률은 어느 정도인가요?",
    answer:
      "다각적 추론 엔진을 통해 여러 번 검증된 문제만을 선별하여 제공하므로 높은 적중률을 자랑합니다. 특히 교수님의 강조 사항을 놓치지 않고 반영합니다.",
  },
  {
    question: "내 자료는 안전하게 보관되나요?",
    answer:
      "물론입니다. 모든 데이터는 엔터프라이즈급 보안 수준으로 암호화되어 관리되며, 사용자의 동의 없이 외부로 유출되지 않습니다.",
  },
]

interface FAQItemProps {
  question: string
  answer: string
  isOpen: boolean
  onToggle: () => void
}

const FAQItem = ({ question, answer, isOpen, onToggle }: FAQItemProps) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    onToggle()
  }
  return (
    <div
      className={`w-full bg-[rgba(231,236,235,0.08)] shadow-[0px_2px_4px_rgba(0,0,0,0.16)] overflow-hidden rounded-[10px] outline outline-1 outline-border outline-offset-[-1px] transition-all duration-500 ease-out cursor-pointer`}
      onClick={handleClick}
    >
      <div className="w-full px-5 py-[18px] pr-4 flex justify-between items-center gap-5 text-left transition-all duration-300 ease-out">
        <div className="flex-1 text-foreground text-base font-medium leading-6 break-words">{question}</div>
        <div className="flex justify-center items-center">
          <ChevronDown
            className={`w-6 h-6 text-muted-foreground-dark transition-all duration-500 ease-out ${isOpen ? "rotate-180 scale-110" : "rotate-0 scale-100"}`}
          />
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-500 ease-out ${isOpen ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"}`}
        style={{
          transitionProperty: "max-height, opacity, padding",
          transitionTimingFunction: "cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <div
          className={`px-5 transition-all duration-500 ease-out ${isOpen ? "pb-[18px] pt-2 translate-y-0" : "pb-0 pt-0 -translate-y-2"}`}
        >
          <div className="text-foreground/80 text-sm font-normal leading-6 break-words">{answer}</div>
        </div>
      </div>
    </div>
  )
}

export function FAQSection() {
  const [openItems, setOpenItems] = useState<Set<number>>(new Set())
  const toggleItem = (index: number) => {
    const newOpenItems = new Set(openItems)
    if (newOpenItems.has(index)) {
      newOpenItems.delete(index)
    } else {
      newOpenItems.add(index)
    }
    setOpenItems(newOpenItems)
  }
  return (
    <section className="w-full pt-[66px] pb-20 md:pb-40 px-5 relative flex flex-col justify-center items-center">
      <div className="w-[300px] h-[500px] absolute top-[150px] left-1/2 -translate-x-1/2 origin-top-left rotate-[-33.39deg] bg-primary/10 blur-[100px] z-0" />
      <div className="self-stretch pt-8 pb-8 md:pt-14 md:pb-14 flex flex-col justify-center items-center gap-2 relative z-10">
        <div className="flex flex-col justify-start items-center gap-4">
          <h2 className="w-full max-w-[435px] text-center text-foreground text-4xl font-semibold leading-10 break-words">
            자주 묻는 질문
          </h2>
          <p className="self-stretch text-center text-muted-foreground text-sm font-medium leading-[18.20px] break-words">
            Everything you need to know about Pointer and how it can transform your development workflow
          </p>
        </div>
      </div>
      <div className="w-full max-w-[600px] pt-0.5 pb-10 flex flex-col justify-start items-start gap-4 relative z-10">
        {faqData.map((faq, index) => (
          <FAQItem key={index} {...faq} isOpen={openItems.has(index)} onToggle={() => toggleItem(index)} />
        ))}
      </div>
    </section>
  )
}
