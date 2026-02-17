import type React from "react"
import type { Metadata } from "next"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Thunder Navigator",
  description: "출제 신호 기반 학습 우선순위 내비게이션",
  generator: "pdflab",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
        <Analytics />
      </body>
    </html>
  )
}
