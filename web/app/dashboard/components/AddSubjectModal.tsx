'use client'

import { useState } from 'react'
import { Plus, X, Loader2 } from 'lucide-react'
import { addSubject } from '../../dashboard/actions'
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function AddSubjectModal({ buttonOnly = false }: { buttonOnly?: boolean }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  // We need to wrap the server action to handle the loading state locally
  async function onSubmit(formData: FormData) {
    setLoading(true)
    try {
        await addSubject(formData)
        setOpen(false)
    } catch (error) {
        console.error(error)
    } finally {
        setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2 rounded-xl bg-primary/90 hover:bg-primary">
            <Plus className="h-4 w-4" />
            과목 추가
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>새 과목 만들기</DialogTitle>
          <DialogDescription>
            분석할 과목 이름을 입력하고 워크스페이스를 생성합니다.
          </DialogDescription>
        </DialogHeader>
        <form action={onSubmit}>
            <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                이름
                </Label>
                <Input
                    id="name"
                    name="name"
                    placeholder="예: 회로이론"
                    className="col-span-3"
                    required
                />
            </div>
            </div>
            <DialogFooter>
            <Button type="submit" disabled={loading}>
                 {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                생성
            </Button>
            </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
