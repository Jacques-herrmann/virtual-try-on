import { computed, ref } from 'vue'

import { api } from '@/api'
import type { LicenseSnapshot } from '@/types'

export const BLOCKED = 'Cette action demande un abonnement actif.'

const license = ref<LicenseSnapshot | null>(null)
const licensed = computed(() => license.value?.state === 'active')

/** État de la licence partagé entre les écrans ; génération et envoi exigent `licensed`. */
export function useLicense() {
  async function load(): Promise<LicenseSnapshot> {
    license.value = await api.license()
    return license.value
  }

  function set(value: LicenseSnapshot) {
    license.value = value
  }

  return { license, licensed, load, set }
}

/** Date de fin de période lisible (« 12 novembre 2026 »). */
export function formatDate(seconds: number | null): string | null {
  if (seconds === null) return null
  return new Date(seconds * 1000).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}
