import { createClient } from "@/utils/supabase/server"
import { redirect } from "next/navigation"
import Link from "next/link"
import { Plus, Book, LogOut, Package2 } from "lucide-react"
import AddSubjectModal from "./components/AddSubjectModal"
import { signout } from "../login/actions"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

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
    <div className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold md:text-2xl">My Subjects</h1>
        <AddSubjectModal />
      </div>

      {subjects && subjects.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject) => (
            <Link href={`/dashboard/${subject.subject_id}`} key={subject.subject_id}>
              <Card className="hover:bg-muted/50 transition-colors cursor-pointer h-full">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-xl font-medium">{subject.name}</CardTitle>
                  <Book className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-xs text-muted-foreground">
                    {new Date(subject.created_at).toLocaleDateString()}
                  </div>
                  <div className="mt-4 flex gap-2">
                    <Badge variant="secondary">Books: 0</Badge>
                    <Badge variant="secondary">Reports: 0</Badge>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed shadow-sm">
          <div className="flex flex-col items-center gap-1 text-center py-20">
            <Book className="h-12 w-12 text-muted-foreground" />
            <h3 className="text-2xl font-bold tracking-tight">No subjects found</h3>
            <p className="text-sm text-muted-foreground">You haven't created any subjects yet.</p>
            <div className="mt-4">
              <AddSubjectModal buttonOnly />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
