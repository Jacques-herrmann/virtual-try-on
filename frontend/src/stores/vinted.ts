import { ref } from 'vue'

import { api } from '@/api'
import { createPoller, useArticles } from '@/stores/articles'
import type { VintedCatalog, VintedStatus } from '@/types'

export const VINTED_POLL_INTERVAL = 2000

/** Un lot ou une connexion est en cours : l'état change, on le suit. */
export function isActive(status: VintedStatus | null): boolean {
  return !!status && (status.batch.running || status.connecting)
}

/** Les statuts des articles changent pendant un lot, et une dernière fois à sa fin. */
export function shouldRefreshArticles(
  previous: VintedStatus | null,
  next: VintedStatus,
): boolean {
  return next.batch.running || !!previous?.batch.running
}

// --- État partagé ------------------------------------------------------------------------

const status = ref<VintedStatus | null>(null)
const catalog = ref<VintedCatalog | null>(null)
let catalogRequest: Promise<VintedCatalog> | null = null

async function apply(next: VintedStatus) {
  const previous = status.value
  status.value = next
  if (shouldRefreshArticles(previous, next)) await useArticles().refresh()
  if (isActive(next)) poller.start()
}

const poller = createPoller(
  async () => apply(await api.vintedStatus()),
  () => isActive(status.value),
  VINTED_POLL_INTERVAL,
)

export function useVinted() {
  async function load() {
    await apply(await api.vintedStatus())
  }

  /** Catalogue Vinted, demandé une seule fois (réessayé après un échec). */
  async function loadCatalog(): Promise<VintedCatalog> {
    if (catalog.value) return catalog.value
    catalogRequest ??= api.vintedCatalog()
    try {
      catalog.value = await catalogRequest
      return catalog.value
    } finally {
      catalogRequest = null
    }
  }

  return {
    status,
    catalog,
    load,
    loadCatalog,
    connect: async () => apply(await api.vintedConnect()),
    disconnect: async () => apply(await api.vintedDisconnect()),
    send: async (ids: string[]) => apply(await api.vintedSend(ids)),
    stop: async () => apply(await api.vintedStop()),
    open: async (id: string) => apply(await api.vintedOpen(id)),
    stopPolling: () => poller.stop(),
  }
}
