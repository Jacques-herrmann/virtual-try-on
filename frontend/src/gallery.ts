// Ordre des photos envoyées sur Vinted (miroir de vto.core.storage).

import type { Article } from './types'

export const MAX_GALLERY = 20

/** Photos utilisables : images de scènes réussies non écartées, puis photos d'origine. */
export function candidates(article: Article): string[] {
  const scenes = article.scenes
    .filter((s) => s.status === 'ok' && s.image && !s.excluded)
    .map((s) => s.image!)
  return [...scenes, ...article.photos]
}

function defaultOrder(article: Article): string[] {
  return candidates(article).filter((p) => !article.photos.includes(p))
}

/** Nouvelle liste où l'élément `from` est déplacé en position `to`. */
export function move<T>(list: T[], from: number, to: number): T[] {
  const next = [...list]
  const [item] = next.splice(from, 1)
  next.splice(Math.min(Math.max(to, 0), next.length), 0, item!)
  return next
}

export function include(list: string[], path: string): string[] {
  if (list.includes(path) || list.length >= MAX_GALLERY) return list
  return [...list, path]
}

/** Retire une photo ; la dernière reste (une annonce Vinted a besoin d'une photo). */
export function remove(list: string[], path: string): string[] {
  return list.length > 1 ? list.filter((p) => p !== path) : list
}

/** Faux si `order` est l'ordre par défaut : rien à enregistrer comme choix du vendeur. */
export function isCustom(article: Article, order: string[]): boolean {
  const fallback = defaultOrder(article)
  return order.length !== fallback.length || order.some((p, i) => p !== fallback[i])
}
