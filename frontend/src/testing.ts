// Données de test partagées par les fichiers *.test.ts.

import type { Article, ArticleStatus } from './types'

export function makeArticle(status: ArticleStatus, changes: Partial<Article> = {}): Article {
  return {
    id: status,
    created_at: '2026-10-10T10:00:00Z',
    status,
    input: { garment_type: 'robe' },
    photos: ['photos/001.jpg'],
    scenes: [],
    listing: null,
    error: null,
    job: null,
    gallery: null,
    effective_gallery: [],
    vinted: null,
    ...changes,
  }
}
