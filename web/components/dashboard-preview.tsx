import { Terminal } from "lucide-react"

export function DashboardPreview() {
  return (
    <div className="w-[calc(100vw-32px)] md:w-[1160px]">
      <div className="bg-zinc-950/50 rounded-xl border border-zinc-800 p-4 shadow-2xl backdrop-blur-sm min-h-[500px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-zinc-500">
          <Terminal className="h-16 w-16" />
          <p className="text-lg font-medium">Dashboard Interface</p>
        </div>
      </div>
    </div>
  )
}
