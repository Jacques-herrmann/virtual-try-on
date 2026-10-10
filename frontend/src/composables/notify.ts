import { useToast } from 'primevue/usetoast'

import { ApiError } from '@/api'

/** Notifications courtes : succès, ou message d'erreur venant de l'API. */
export function useNotify() {
  const toast = useToast()

  function success(summary: string) {
    toast.add({ severity: 'success', summary, life: 2500 })
  }

  function error(e: unknown) {
    if (e instanceof ApiError && e.status === 0) return // déjà signalé par le bandeau
    const detail = e instanceof ApiError ? e.message : 'Une erreur inattendue est survenue.'
    toast.add({ severity: 'error', summary: 'Oups', detail, life: 6000 })
  }

  return { success, error }
}
