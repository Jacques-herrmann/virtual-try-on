import { ref } from 'vue'

import { api } from '@/api'
import { useSettings } from '@/stores/settings'
import type { TutorialState } from '@/types'

/** Vrai pendant que la vidéo de présentation est affichée : aucune visite ne démarre. */
const videoOpen = ref(false)

/** Ce que le vendeur a déjà vu (vidéo, visites), enregistré dans les réglages. */
export function useTutorial() {
  const { settings } = useSettings()

  /**
   * Met à jour l'état localement tout de suite, puis l'enregistre. Un échec ne bloque rien :
   * au pire, la vidéo ou la visite revient au prochain lancement.
   */
  async function save(changes: Partial<TutorialState>) {
    if (!settings.value) return
    const tutorial = { ...settings.value.tutorial, ...changes }
    settings.value = { ...settings.value, tutorial }
    try {
      await api.updateSettings({ tutorial })
    } catch (e) {
      console.warn("Progression du tutoriel non enregistrée", e)
    }
  }

  function tourSeen(id: string): boolean {
    // Réglages pas encore chargés : on ne lance rien.
    return settings.value?.tutorial.tours_seen.includes(id) ?? true
  }

  async function markTourSeen(id: string) {
    const seen = settings.value?.tutorial.tours_seen
    if (!seen || seen.includes(id)) return
    await save({ tours_seen: [...seen, id] })
  }

  return { settings, videoOpen, save, tourSeen, markTourSeen }
}
