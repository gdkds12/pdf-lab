'use server'

import { createClient } from "@/utils/supabase/server"
import { Storage } from "@google-cloud/storage"
import { JobsClient } from "@google-cloud/run"
import { revalidatePath } from "next/cache"

// Init GCS
// Ensure GOOGLE_APPLICATION_CREDENTIALS or gcloud auth is set in environment
const storage = new Storage({
    projectId: 'pdf-lab-468815',
})
const bucketName = 'project-thunder-assets-pdf-lab-468815'
const jobName = `projects/pdf-lab-468815/locations/asia-northeast3/jobs/thunder-worker`
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const NIL_UUID = "00000000-0000-0000-0000-000000000000"

async function runThunderJob(args: string[]) {
    const runClient = new JobsClient()
    const maxAttempts = 3

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            await runClient.runJob({
                name: jobName,
                overrides: {
                    containerOverrides: [{ args }]
                }
            })
            return
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            const retryable = /429|resource exhausted|quota|rate limit|timeout|unavailable|503/i.test(message)
            if (!retryable || attempt === maxAttempts) {
                throw error
            }

            const delayMs = Math.min(5000, 500 * (2 ** (attempt - 1)))
            await new Promise((resolve) => setTimeout(resolve, delayMs))
        }
    }
}

function assertUuid(value: string, fieldName: string): string {
    const trimmed = (value || "").trim()
    if (!UUID_PATTERN.test(trimmed) || trimmed.toLowerCase() === NIL_UUID) {
        throw new Error(`Invalid ${fieldName} UUID`)
    }
    return trimmed
}

function assertUuidList(values: string[], fieldName: string): string[] {
    if (!Array.isArray(values) || values.length === 0) {
        throw new Error(`Missing ${fieldName}`)
    }
    return values.map((v) => assertUuid(v, fieldName))
}

function parseGcsUri(gcsUri: string): { bucket: string, path: string } {
    if (!gcsUri.startsWith("gs://")) {
        throw new Error(`Invalid GCS URI: ${gcsUri}`)
    }
    const raw = gcsUri.slice(5)
    const firstSlash = raw.indexOf("/")
    if (firstSlash <= 0) {
        throw new Error(`Invalid GCS URI: ${gcsUri}`)
    }
    const bucket = raw.slice(0, firstSlash)
    const path = raw.slice(firstSlash + 1)
    if (!path) {
        throw new Error(`Invalid GCS URI: ${gcsUri}`)
    }
    return { bucket, path }
}

export async function getSignedUploadUrl({ fileName, contentType }: { fileName: string, contentType: string }) {
    'use server'

    if (!contentType.startsWith('audio/')) {
        throw new Error('Only audio uploads are allowed via server signed URL')
    }
    
    // GCS Signed URL generation
    const options = {
        version: 'v4' as const,
        action: 'write' as const,
        expires: Date.now() + 15 * 60 * 1000, // 15 minutes
        contentType: contentType,
    };

    try {
        const [url] = await storage
            .bucket(bucketName)
            .file(fileName)
            .getSignedUrl(options);
            
        return { url, gcsPath: `gs://${bucketName}/${fileName}` }
    } catch (error) {
        console.error("Error generating signed URL:", error)
        throw new Error("Failed to generate upload URL")
    }
}

export async function createSourceAndTrigger(subjectId: string, title: string, gcsPath: string) {
    'use server'
    throw new Error("Deprecated: textbook uploads must go directly from client to Gemini")
}

export async function createSourceFromGeminiFile(subjectId: string, title: string, geminiFileUri: string) {
    'use server'
    const safeSubjectId = assertUuid(subjectId, "subjectId")
    const safeTitle = (title || "").trim() || "Textbook"
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) throw new Error("Unauthorized")

    if (!geminiFileUri.startsWith('https://generativelanguage.googleapis.com/') && !geminiFileUri.startsWith('files/')) {
        throw new Error("Invalid Gemini file URI")
    }

    const { data: source, error } = await supabase.from('sources').insert({
        user_id: user.id,
        subject_id: safeSubjectId,
        kind: 'textbook',
        title: safeTitle,
        gcs_pdf_url: geminiFileUri,
        ingest_status: 'succeeded'
    }).select().single()

    if (error) {
        console.error("DB Insert Error:", error)
        throw new Error("Failed to create source record")
    }

    revalidatePath(`/dashboard/${safeSubjectId}`)

    return { success: true, sourceId: source.source_id }
}

export async function createSessionAndTrigger(subjectId: string, title: string, gcsPath: string) {
    'use server'
    const safeSubjectId = assertUuid(subjectId, "subjectId")
    parseGcsUri(gcsPath)
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error("Unauthorized")

    // 1. Insert Session
    const { data: session, error: sessError } = await supabase.from('sessions').insert({
        user_id: user.id,
        subject_id: safeSubjectId,
        exam_window: 'midterm', // Default for test
        gcs_audio_url: gcsPath,
        status: 'queued'
    }).select().single()

    if (sessError) {
        console.error("DB Session Insert Error:", sessError)
        throw new Error("Failed to create session record")
    }

    // 3. Trigger Job Phase 2 (Splitter Mode)
    // The splitter will handle chunk creation and dispatching worker jobs
    try {
        await runThunderJob(['--phase', 'split', '--job-payload', JSON.stringify({
            session_id: session.session_id,
            gcs_audio_url: gcsPath,
            subject: title,
            exam_window: 'midterm'
        })])
        
        console.log(`Triggered Splitter Job for session ${session.session_id}`);
    } catch (jobError) {
        console.error("Failed to trigger Cloud Run Job:", jobError);
        throw new Error("Failed to start processing job.");
    }

    revalidatePath(`/dashboard/${safeSubjectId}`)
    return { success: true }
}

export async function deleteSourceItem(id: string, type: 'pdf' | 'audio') {
    'use server'
    const safeId = assertUuid(id, "id")
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error("Unauthorized")

    try {
        if (type === 'pdf') {
            const { data: source } = await supabase
                .from('sources')
                .select('gcs_pdf_url')
                .eq('source_id', safeId)
                .eq('user_id', user.id)
                .single()

            await supabase.from('sources').delete().eq('source_id', safeId).eq('user_id', user.id)

            if (source?.gcs_pdf_url) {
                try {
                    const target = parseGcsUri(source.gcs_pdf_url)
                    await storage.bucket(target.bucket).file(target.path).delete()
                } catch (gcsErr) {
                    console.warn("PDF asset delete failed (continuing):", gcsErr)
                }
            }
        } else {
            const { data: session } = await supabase
                .from('sessions')
                .select('gcs_audio_url')
                .eq('session_id', safeId)
                .eq('user_id', user.id)
                .single()

            await supabase.from('sessions').delete().eq('session_id', safeId).eq('user_id', user.id)

            if (session?.gcs_audio_url) {
                try {
                    const target = parseGcsUri(session.gcs_audio_url)
                    await storage.bucket(target.bucket).file(target.path).delete()
                } catch (gcsErr) {
                    console.warn("Audio asset delete failed (continuing):", gcsErr)
                }
            }
        }
        revalidatePath(`/dashboard`) 
        // Revalidate specific path too if we had subjectId passed, but dashboard parent might be enough depending on structure? 
        // Actually best to revalidate the exact page if possible, but we don't have subjectId here easily without prop.
        // Let's rely on client-side state update mostly or pass subjectId.
        // Updating signature to include subjectId for revalidation.
        return { success: true }
    } catch (e) {
        console.error("Delete failed:", e)
        return { success: false, error: "Delete failed" }
    }
}

export async function createReportJob(subjectId: string, sessionIds: string[]) {
    'use server'
    const safeSubjectId = assertUuid(subjectId, "subjectId")
    const safeSessionIds = assertUuidList(sessionIds, "sessionIds")
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error("Unauthorized")
    const { data: sessions, error: sessErr } = await supabase
        .from('sessions')
        .select('session_id, status')
        .in('session_id', safeSessionIds)
        .eq('user_id', user.id)

    if (sessErr) {
        throw new Error("Failed to validate session status")
    }
    if (!sessions || sessions.length !== safeSessionIds.length) {
        throw new Error("Some selected sessions were not found or are not accessible")
    }

    const allowed = new Set(["reasoning", "completed"])
    const blocked = (sessions || []).filter(s => !allowed.has(s.status)).map(s => `${s.session_id}:${s.status}`)
    if (blocked.length > 0) {
        throw new Error(`Sessions not ready for report: ${blocked.join(", ")}`)
    }

    // 1. Trigger Cloud Run Job (Phase 4 - Aggregate Reasoning)
    try {
        await runThunderJob(['--phase', '4', '--job-payload', JSON.stringify({
            subject_id: subjectId,
            session_ids: safeSessionIds,
            exam_window: 'midterm' // Could be passed from UI
        })])
        
        console.log(`Triggered Report Job for subject ${safeSubjectId} with sessions: ${safeSessionIds.length}`);
    } catch (jobError) {
        console.error("Failed to trigger Report Job:", jobError);
        throw new Error("Failed to start createReportJob.");
    }
    
    revalidatePath(`/dashboard/${safeSubjectId}`)
    return { success: true }
}

export async function retrySourceItem(id: string, type: 'pdf' | 'audio') {
    'use server'
    const safeId = assertUuid(id, "id")
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error("Unauthorized")

    if (type === 'pdf') {
        const { data: source, error } = await supabase
            .from('sources')
            .select('source_id, subject_id, gcs_pdf_url')
            .eq('source_id', safeId)
            .eq('user_id', user.id)
            .single()
        if (error || !source) throw new Error("Source not found")
        if (!source.gcs_pdf_url) throw new Error("Source has no GCS PDF URL")

        const { error: updateError } = await supabase
            .from('sources')
            .update({ ingest_status: 'queued', page_count: null })
            .eq('source_id', safeId)
            .eq('user_id', user.id)
        if (updateError) throw new Error("Failed to reset source status")

        await runThunderJob(['--phase', '1', '--job-payload', JSON.stringify({
            source_id: source.source_id,
            gcs_pdf_url: source.gcs_pdf_url
        })])
        revalidatePath(`/dashboard/${source.subject_id}`)
        return { success: true }
    }

    const { data: session, error: sessErr } = await supabase
        .from('sessions')
        .select('session_id, subject_id, gcs_audio_url, exam_window')
        .eq('session_id', safeId)
        .eq('user_id', user.id)
        .single()
    if (sessErr || !session) throw new Error("Session not found")
    if (!session.gcs_audio_url) throw new Error("Session has no GCS audio URL")

    // Clean previous run artifacts for this session.
    await supabase.from('session_reports').delete().eq('session_id', safeId)
    await supabase.from('evidence_candidates').delete().eq('session_id', safeId)
    await supabase.from('audio_chunks').delete().eq('session_id', safeId)
    await supabase.from('sessions').update({ status: 'queued', logs: [] }).eq('session_id', safeId).eq('user_id', user.id)

    const subjectLabel = session.gcs_audio_url.split('/').pop() || 'Audio'
    await runThunderJob(['--phase', 'split', '--job-payload', JSON.stringify({
        session_id: session.session_id,
        gcs_audio_url: session.gcs_audio_url,
        subject: subjectLabel,
        exam_window: session.exam_window || 'midterm'
    })])

    revalidatePath(`/dashboard/${session.subject_id}`)
    return { success: true }
}
