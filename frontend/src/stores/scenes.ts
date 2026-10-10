import { ref } from 'vue'

import { api } from '@/api'
import type { SceneInfo } from '@/types'

const scenes = ref<SceneInfo[]>([])

/** Liste des scènes, partagée (noms affichés dans la relecture, écran Scènes). */
export function useScenes() {
  async function load() {
    scenes.value = await api.listScenes()
    return scenes.value
  }

  function nameOf(slug: string): string {
    return scenes.value.find((s) => s.slug === slug)?.name ?? slug
  }

  return { scenes, load, nameOf }
}
