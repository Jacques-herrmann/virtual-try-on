import { computed, ref } from 'vue'

import { api } from '@/api'
import type { Article, ArticleStatus, QueueStatus } from '@/types'

export const POLL_INTERVAL = 1500

const BUSY: ArticleStatus[] = ['queued', 'generating']

export function isBusy(articles: Article[]): boolean {
  return articles.some((a) => BUSY.includes(a.status))
}

export type Panel = 'form' | 'draft' | 'progress' | 'review' | 'validated' | 'error'

/** Panneau à afficher à droite selon l'article sélectionné (aucun = nouvel article). */
export function panelFor(article: Article | null | undefined): Panel {
  if (!article) return 'form'
  switch (article.status) {
    case 'draft':
      return 'draft'
    case 'queued':
    case 'generating':
      return 'progress'
    case 'to_review':
      return 'review'
    case 'validated':
    case 'published':
      return 'validated'
    case 'error':
      return 'error'
  }
}

/** L'API refuse de supprimer un article en cours de génération. */
export function deletable(article: Article): boolean {
  return !BUSY.includes(article.status)
}

/** Sélection débarrassée des articles qui n'existent plus. */
export function pruneSelection(selected: string[], articles: Article[]): string[] {
  const ids = new Set(articles.map((a) => a.id))
  return selected.filter((id) => ids.has(id))
}

export const FILTERS = [
  { key: 'all', label: 'Tous', statuses: null },
  { key: 'busy', label: 'En cours', statuses: BUSY },
  { key: 'review', label: 'À relire', statuses: ['to_review'] },
  { key: 'validated', label: 'Validés', statuses: ['validated', 'published'] },
  { key: 'error', label: 'Erreur', statuses: ['error'] },
] as const satisfies readonly { key: string; label: string; statuses: ArticleStatus[] | null }[]

export type FilterKey = (typeof FILTERS)[number]['key']

export function matches(filter: FilterKey, article: Article): boolean {
  const statuses = FILTERS.find((f) => f.key === filter)!.statuses as ArticleStatus[] | null
  return statuses === null || statuses.includes(article.status)
}

/**
 * Appelle `tick` toutes les `interval` ms tant que `shouldContinue()` est vrai après l'appel.
 * `start()` relance la boucle si elle est arrêtée (sans en créer une seconde).
 */
export function createPoller(
  tick: () => Promise<void>,
  shouldContinue: () => boolean,
  interval = POLL_INTERVAL,
) {
  let timer: ReturnType<typeof setTimeout> | null = null
  let stopped = false

  async function run() {
    timer = null
    try {
      await tick()
    } catch {
      // erreur déjà signalée (bandeau ou notification) : on réessaie au prochain tour
    }
    if (!stopped && shouldContinue()) timer = setTimeout(run, interval)
  }

  return {
    start() {
      stopped = false
      if (timer === null) timer = setTimeout(run, interval)
    },
    stop() {
      stopped = true
      if (timer !== null) clearTimeout(timer)
      timer = null
    },
    get running() {
      return timer !== null
    },
  }
}

// --- État partagé ------------------------------------------------------------------------

const articles = ref<Article[]>([])
const queue = ref<QueueStatus | null>(null)
// Version d'affichage des images : change quand un article sort de la génération, pour que
// le navigateur recharge des images régénérées qui gardent le même nom.
const imageVersions = ref<Record<string, string>>({})

function bumpChanged(previous: Article[], next: Article[]) {
  const before = new Map(previous.map((a) => [a.id, a.status]))
  for (const article of next) {
    const old = before.get(article.id)
    if (old !== article.status) imageVersions.value[article.id] = String(Date.now())
  }
}

async function refresh() {
  const [list, status] = await Promise.all([api.listArticles(), api.queue()])
  bumpChanged(articles.value, list)
  articles.value = list
  queue.value = status
}

const poller = createPoller(refresh, () => isBusy(articles.value))

export function useArticles() {
  /** Remplace un article dans la liste après une action, et relance le suivi si besoin. */
  function upsert(article: Article) {
    const i = articles.value.findIndex((a) => a.id === article.id)
    bumpChanged(i >= 0 ? [articles.value[i]!] : [], [article])
    if (i >= 0) articles.value[i] = article
    else articles.value.unshift(article)
    if (isBusy([article])) poller.start()
  }

  function remove(id: string) {
    articles.value = articles.value.filter((a) => a.id !== id)
  }

  async function load() {
    await refresh()
    if (isBusy(articles.value)) poller.start()
  }

  return {
    articles,
    queue,
    imageVersions,
    busy: computed(() => isBusy(articles.value)),
    load,
    refresh,
    upsert,
    remove,
    startPolling: () => poller.start(),
    stopPolling: () => poller.stop(),
  }
}
