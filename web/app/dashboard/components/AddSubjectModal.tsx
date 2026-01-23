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
        <Button className="gap-2">
            <Plus className="h-4 w-4" />
            Add Subject
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Add New Subject</DialogTitle>
          <DialogDescription>
            Create a new subject to start tracking your exams and materials.
          </DialogDescription>
        </DialogHeader>
        <form action={onSubmit}>
            <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                Name
                </Label>
                <Input
                    id="name"
                    name="name"
                    placeholder="e.g., Electromagnetics"
                    className="col-span-3"
                    required
                />
            </div>
            </div>
            <DialogFooter>
            <Button type="submit" disabled={loading}>
                 {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Create Subject
            </Button>
            </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
