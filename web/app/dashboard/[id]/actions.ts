'use server'

import { createClient } from "@/utils/supabase/server"
import { Storage } from "@google-cloud/storage"
import { JobsClient } from "@google-cloud/run"
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

    // 2. Trigger Cloud Run Job
    try {
        const runClient = new JobsClient();
        const jobName = `projects/pdf-lab-468815/locations/asia-northeast3/jobs/thunder-worker`;
        
        await runClient.runJob({
            name: jobName,
            overrides: {
                containerOverrides: [
                    {
                        args: ['--phase', '1', '--job-payload', JSON.stringify({
                            source_id: source.source_id,
                            gcs_pdf_url: gcsPath
                        })]
                    }
                ]
            }
        });
        
        console.log(`Triggered Cloud Run Job: ${jobName} for source ${source.source_id}`);
    } catch (jobError) {
        console.error("Failed to trigger Cloud Run Job:", jobError);
        throw new Error("Failed to start processing job. Please try again.");
    }
    
    // Trigger Revalidation
    revalidatePath(`/dashboard/${subjectId}`)
    
    return { success: true, sourceId: source.source_id }
}

export async function createSessionAndTrigger(subjectId: string, title: string, gcsPath: string) {
    'use server'
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error("Unauthorized")

    // 1. Insert Session
    const { data: session, error: sessError } = await supabase.from('sessions').insert({
        user_id: user.id,
        subject_id: subjectId,
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
        const runClient = new JobsClient();
        const jobName = `projects/pdf-lab-468815/locations/asia-northeast3/jobs/thunder-worker`;
        
        await runClient.runJob({
            name: jobName,
            overrides: {
                containerOverrides: [
                    {
                        args: ['--phase', 'split', '--job-payload', JSON.stringify({
                            session_id: session.session_id,
                            gcs_audio_url: gcsPath,
                            subject: title,
                            exam_window: 'midterm'
                        })]
                    }
                ]
            }
        });
        
        console.log(`Triggered Splitter Job for session ${session.session_id}`);
    } catch (jobError) {
        console.error("Failed to trigger Cloud Run Job:", jobError);
        throw new Error("Failed to start processing job.");
    }

    revalidatePath(`/dashboard/${subjectId}`)
    return { success: true }
}

export async function createReportJob(subjectId: string, sessionIds: string[]) {
    'use server'
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error("Unauthorized")
    if (!sessionIds || sessionIds.length === 0) throw new Error("No sessions selected")

    // 1. Trigger Cloud Run Job (Phase 4 - Aggregate Reasoning)
    try {
        const runClient = new JobsClient();
        const jobName = `projects/pdf-lab-468815/locations/asia-northeast3/jobs/thunder-worker`;
        
        await runClient.runJob({
            name: jobName,
            overrides: {
                containerOverrides: [
                    {
                        args: ['--phase', '4', '--job-payload', JSON.stringify({
                            subject_id: subjectId,
                            session_ids: sessionIds,
                            exam_window: 'midterm' // Could be passed from UI
                        })]
                    }
                ]
            }
        });
        
        console.log(`Triggered Report Job for subject ${subjectId} with sessions: ${sessionIds.length}`);
    } catch (jobError) {
        console.error("Failed to trigger Report Job:", jobError);
        throw new Error("Failed to start createReportJob.");
    }
    
    revalidatePath(`/dashboard/${subjectId}`)
    return { success: true }
}
