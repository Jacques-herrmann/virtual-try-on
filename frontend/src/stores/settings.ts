import { ref } from 'vue'

import { api } from '@/api'
import type { SettingsView } from '@/types'

const settings = ref<SettingsView | null>(null)

/** Réglages partagés entre les écrans (chargés une fois, rafraîchis après chaque modification). */
export function useSettings() {
  async function load(): Promise<SettingsView> {
    settings.value = await api.settings()
    return settings.value
  }

  function set(value: SettingsView) {
    settings.value = value
  }

  return { settings, load, set }
}
