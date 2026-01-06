import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"
import DashboardLayout from "./components/DashboardLayout"

export default async function SubjectPage({ params }: { params: { id: string } }) {
  // await params for Next.js 15
  const { id } = await params
  const supabase = await createClient()

  // 과목 정보 확인 및 권한 체크
  const { data: subject, error } = await supabase
    .from('subjects')
    .select('*')
    .eq('subject_id', id)
    .single()

  if (error || !subject) {
    redirect('/dashboard')
  }

  return (
    <DashboardLayout subject={subject} />
  )
}
