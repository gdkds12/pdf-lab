'use server'

import { createClient } from "@/utils/supabase/server"
import { Storage } from "@google-cloud/storage"
import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

// Init GCS
// Ensure GOOGLE_APPLICATION_CREDENTIALS or gcloud auth is set in environment
const storage = new Storage({
    projectId: 'pdf-lab-468815',
})
const bucketName = 'project-thunder-assets-pdf-lab-468815'

export async function getSignedUploadUrl({ fileName, contentType }: { fileName: string, contentType: string }) {
    'use server'
    
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
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error("Unauthorized")

    // 1. Insert Source
    const { data: source, error } = await supabase.from('sources').insert({
        user_id: user.id,
        subject_id: subjectId,
        kind: 'textbook', // Default for now
        title: title,
        gcs_pdf_url: gcsPath,
        ingest_status: 'queued'
    }).select().single()

    if (error) {
        console.error("DB Insert Error:", error)
        throw new Error("Failed to create source record")
    }

    // 2. Trigger Cloud Run Job (Optional / Future)
    // For MVP Phase 1 Local, we just insert.
    // In production, we would use Cloud Tasks or Pub/Sub here.
    
    // Trigger Revalidation
    revalidatePath(`/dashboard/${subjectId}`)
    
    return { success: true, sourceId: source.source_id }
}
