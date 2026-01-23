"use client"

import { Twitter, Github, Linkedin } from "lucide-react"

export function FooterSection() {
  return (
    <footer className="w-full max-w-[1320px] mx-auto px-5 flex flex-col md:flex-row justify-between items-start gap-8 md:gap-0 py-10 md:py-[70px]">
      {/* Left Section: Logo, Description, Social Links */}
      <div className="flex flex-col justify-start items-start gap-8 p-4 md:p-8">
        <div className="flex gap-3 items-stretch justify-center">
          <div className="text-center text-foreground text-xl font-semibold leading-4">Project Thunder</div>
        </div>
        <p className="text-foreground/90 text-sm font-medium leading-[18px] text-left">A+를 향한 지름길</p>
        <div className="flex justify-start items-start gap-3">
          <a href="#" aria-label="Twitter" className="w-4 h-4 flex items-center justify-center">
            <Twitter className="w-full h-full text-muted-foreground" />
          </a>
          <a href="#" aria-label="GitHub" className="w-4 h-4 flex items-center justify-center">
            <Github className="w-full h-full text-muted-foreground" />
          </a>
          <a href="#" aria-label="LinkedIn" className="w-4 h-4 flex items-center justify-center">
            <Linkedin className="w-full h-full text-muted-foreground" />
          </a>
        </div>
      </div>
      {/* Right Section: Product, Company, Resources */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-8 md:gap-12 p-4 md:p-8 w-full md:w-auto">
        <div className="flex flex-col justify-start items-start gap-3">
          <h3 className="text-muted-foreground text-sm font-medium leading-5">제품</h3>
          <div className="flex flex-col justify-end items-start gap-2">
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              기능 소개
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              요금 안내
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              자료 연동
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              실시간 분석
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              다각적 추론
            </a>
          </div>
        </div>
        <div className="flex flex-col justify-start items-start gap-3">
          <h3 className="text-muted-foreground text-sm font-medium leading-5">회사</h3>
          <div className="flex flex-col justify-center items-start gap-2">
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              소개
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              팀
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              채용
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              브랜드
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              문의
            </a>
          </div>
        </div>
        <div className="flex flex-col justify-start items-start gap-3">
          <h3 className="text-muted-foreground text-sm font-medium leading-5">리소스</h3>
          <div className="flex flex-col justify-center items-start gap-2">
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              이용약관
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              개인정보처리방침
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              문서
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              커뮤니티
            </a>
            <a href="#" className="text-foreground text-sm font-normal leading-5 hover:underline">
              기술 지원
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
