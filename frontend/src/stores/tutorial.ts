import { ref } from 'vue'

import { api } from '@/api'
import { useSettings } from '@/stores/settings'
import type { TutorialState } from '@/types'

/** Vrai pendant que la vidéo de présentation est affichée : aucune visite ne démarre. */
const videoOpen = ref(false)

export const INTRO_VIDEO = {
  src: '/tutorial/kaloe.mp4',
  captions: '/tutorial/kaloe.vtt',
  poster: '/tutorial/kaloe.jpg',
  title: 'Kaloé en 1 minute',
}

export const KEY_VIDEO = {
  src: '/tutorial/cle-gemini.mp4',
  captions: '/tutorial/cle-gemini.vtt',
  title: 'Créer ta clé Gemini',
}

/** Le serveur renvoie la page de l'app pour un fichier absent : on vérifie le type reçu. */
export async function videoAvailable(src: string): Promise<boolean> {
  try {
    const r = await fetch(src, { headers: { Range: 'bytes=0-0' } })
    return r.ok && (r.headers.get('content-type') ?? '').startsWith('video/')
  } catch {
    return false
  }
}

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

  /** Fermeture de la vidéo de présentation, quelle qu'en soit la façon : elle est vue. */
  async function closeIntro() {
    videoOpen.value = false
    if (settings.value && !settings.value.tutorial.video_seen) await save({ video_seen: true })
  }

  return { settings, videoOpen, save, tourSeen, markTourSeen, closeIntro }
}
