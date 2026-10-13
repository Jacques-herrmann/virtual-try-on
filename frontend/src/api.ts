// Client de l'API locale. Toute erreur devient une ApiError avec un message en français.

import { ref } from 'vue'

import type {
  Article,
  ArticleStatus,
  LicenseSnapshot,
  Listing,
  QueueStatus,
  SceneDetail,
  SceneInfo,
  SettingsView,
  UpdateProgress,
  UpdateSnapshot,
  UserInput,
  VintedCatalog,
  VintedStatus,
} from './types'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

const UNREACHABLE = "L'application ne répond plus. Ferme-la et relance-la."

/** Passe à true dès qu'une requête n'obtient aucune réponse du serveur local. */
export const disconnected = ref(false)

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' }
  if (body instanceof FormData) {
    init.body = body
  } else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }

  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    disconnected.value = true
    throw new ApiError(UNREACHABLE, 0)
  }
  disconnected.value = false

  if (!response.ok) {
    let message = 'Une erreur inattendue est survenue.'
    try {
      const data = await response.json()
      if (typeof data?.message === 'string') message = data.message
    } catch {
      // corps vide ou non JSON : message générique
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function form(fields: Record<string, unknown>, fileField: string, files: File[]): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value !== null && value !== undefined && value !== '') data.append(key, String(value))
  }
  for (const file of files) data.append(fileField, file, file.name)
  return data
}

const enc = encodeURIComponent

export const api = {
  // Articles
  listArticles: (status?: ArticleStatus) =>
    request<Article[]>('GET', `/api/articles${status ? `?status=${status}` : ''}`),
  getArticle: (id: string) => request<Article>('GET', `/api/articles/${enc(id)}`),
  createArticle: (input: UserInput, photos: File[]) =>
    request<Article>('POST', '/api/articles', form({ ...input }, 'photos', photos)),
  updateInput: (id: string, input: UserInput) =>
    request<Article>('PATCH', `/api/articles/${enc(id)}/input`, input),
  updateListing: (id: string, listing: Listing) =>
    request<Article>('PATCH', `/api/articles/${enc(id)}/listing`, listing),
  setGallery: (id: string, gallery: string[] | null) =>
    request<Article>('PATCH', `/api/articles/${enc(id)}/gallery`, { gallery }),
  setExcluded: (id: string, scene: string, excluded: boolean) =>
    request<Article>('PATCH', `/api/articles/${enc(id)}/scenes/${enc(scene)}`, { excluded }),
  generate: (id: string, what?: { scenes?: string[]; listing?: boolean }) =>
    request<Article>('POST', `/api/articles/${enc(id)}/generate`, what),
  cancel: (id: string) => request<Article>('POST', `/api/articles/${enc(id)}/cancel`),
  validate: (id: string) => request<Article>('POST', `/api/articles/${enc(id)}/validate`),
  unvalidate: (id: string) => request<Article>('POST', `/api/articles/${enc(id)}/unvalidate`),
  deleteArticle: (id: string) => request<void>('DELETE', `/api/articles/${enc(id)}`),

  // File de génération
  queue: () => request<QueueStatus>('GET', '/api/queue'),
  resumeQueue: () => request<QueueStatus>('POST', '/api/queue/resume'),

  // Vinted
  vintedStatus: () => request<VintedStatus>('GET', '/api/vinted/status'),
  vintedConnect: () => request<VintedStatus>('POST', '/api/vinted/connect'),
  vintedDisconnect: () => request<VintedStatus>('POST', '/api/vinted/disconnect'),
  vintedStop: () => request<VintedStatus>('POST', '/api/vinted/stop'),
  vintedSend: (articleIds: string[]) =>
    request<VintedStatus>('POST', '/api/vinted/send', { article_ids: articleIds }),
  vintedOpen: (articleId: string) =>
    request<VintedStatus>('POST', '/api/vinted/open', { article_id: articleId }),
  vintedCatalog: () => request<VintedCatalog>('GET', '/api/vinted/catalog'),

  // Réglages
  settings: () => request<SettingsView>('GET', '/api/settings'),
  updateSettings: (changes: Partial<Omit<SettingsView, 'has_key' | 'key_hint'>>) =>
    request<SettingsView>('PUT', '/api/settings', changes),
  resetListingPrompt: () => request<SettingsView>('POST', '/api/settings/reset-listing-prompt'),
  checkKey: (key: string) => request<SettingsView>('POST', '/api/settings/check-key', { key }),
  openLogs: () => request<void>('POST', '/api/system/open-logs'),

  // Licence
  license: () => request<LicenseSnapshot>('GET', '/api/license'),
  activateLicense: (key: string) => request<LicenseSnapshot>('POST', '/api/license', { key }),
  deactivateLicense: () => request<LicenseSnapshot>('DELETE', '/api/license'),
  licensePortal: () => request<{ url: string }>('GET', '/api/license/portal'),
  licenseRenew: () => request<{ url: string }>('GET', '/api/license/renew'),

  // Mises à jour
  update: () => request<UpdateSnapshot>('GET', '/api/update'),
  installUpdate: () => request<UpdateProgress>('POST', '/api/update/install'),
  updateProgress: () => request<UpdateProgress>('GET', '/api/update/progress'),

  // Scènes
  listScenes: () => request<SceneInfo[]>('GET', '/api/scenes'),
  getScene: (slug: string) => request<SceneDetail>('GET', `/api/scenes/${enc(slug)}`),
  createScene: (name: string) => request<SceneDetail>('POST', '/api/scenes', { name }),
  updateScene: (
    slug: string,
    changes: Partial<Pick<SceneDetail, 'name' | 'enabled' | 'order' | 'prompt'>>,
  ) => request<SceneDetail>('PATCH', `/api/scenes/${enc(slug)}`, changes),
  deleteScene: (slug: string) => request<void>('DELETE', `/api/scenes/${enc(slug)}`),
  addBackgrounds: (slug: string, files: File[], subfolder: string | null) =>
    request<SceneDetail>(
      'POST',
      `/api/scenes/${enc(slug)}/backgrounds`,
      form({ subfolder }, 'files', files),
    ),
  deleteBackground: (slug: string, path: string) =>
    request<void>(
      'DELETE',
      `/api/scenes/${enc(slug)}/backgrounds/${path.split('/').map(enc).join('/')}`,
    ),
}

/** URL d'une image d'article ; `version` force le rechargement après une régénération. */
export function articleFile(article: Article, path: string, version?: string): string {
  const url = `/files/articles/${enc(article.id)}/${path.split('/').map(enc).join('/')}`
  return version ? `${url}?v=${enc(version)}` : url
}

export function sceneFile(slug: string, path: string): string {
  return `/files/scenes/${enc(slug)}/backgrounds/${path.split('/').map(enc).join('/')}`
}
