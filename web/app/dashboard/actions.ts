'use server'

import { createClient } from '@/utils/supabase/server'
import { revalidatePath } from 'next/cache'

export async function addSubject(formData: FormData) {

  const name = formData.get('name') as string
  const supabase = await createClient()

  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return { error: 'Not authenticated' }
  }

  const { error } = await supabase
    .from('subjects')
    .insert({ name, user_id: user.id })

  if (error) {
    return { error: error.message }
  }

  revalidatePath('/dashboard')
  return { message: 'Subject added successfully' }
}
