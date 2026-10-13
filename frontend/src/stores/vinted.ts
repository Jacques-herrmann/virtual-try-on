import { ref } from 'vue'

import { api } from '@/api'
import { createPoller, useArticles } from '@/stores/articles'
import type { Article, VintedCatalog, VintedStatus } from '@/types'

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

export interface Badge {
  label: string
  severity: 'success' | 'info' | 'warn' | 'danger'
  icon?: string
  /** Détail affiché au survol. */
  detail?: string
}

/** Badge Vinted d'un article (remplace celui du statut), ou null s'il n'a pas été envoyé. */
export function vintedBadge(article: Article): Badge | null {
  const result = article.vinted
  if (!result) return null
  switch (result.status) {
    case 'error':
      return {
        label: 'Échec de l’envoi',
        severity: 'danger',
        icon: 'icon-triangle-alert',
        detail: result.error ?? undefined,
      }
    case 'partial':
      return {
        label: 'À compléter sur Vinted',
        severity: 'warn',
        detail: `À compléter : ${result.missing_fields.join(', ')}`,
      }
    case 'ok':
      return result.mode === 'publish'
        ? { label: 'Publié sur Vinted', severity: 'success', icon: 'icon-circle-check' }
        : { label: 'Brouillon Vinted', severity: 'info' }
  }
}

/** Seuls les articles validés partent sur Vinted (y compris après un échec). */
export function sendable(article: Article): boolean {
  return article.status === 'validated'
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
