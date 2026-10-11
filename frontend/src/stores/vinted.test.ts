import { describe, expect, it } from 'vitest'

import { makeArticle } from '@/testing'
import type { VintedResult, VintedStatus } from '@/types'

import { isActive, pruneSelection, sendable, shouldRefreshArticles, vintedBadge } from './vinted'

function status(changes: { running?: boolean; connecting?: boolean } = {}): VintedStatus {
  return {
    connected: true,
    connecting: changes.connecting ?? false,
    data_revision: 'r1',
    data_source: 'remote',
    batch: {
      running: changes.running ?? false,
      paused_reason: null,
      current: null,
      done: 0,
      total: 0,
      failed: 0,
      message: null,
    },
  }
}

describe('isActive', () => {
  it('suit un lot ou une connexion en cours', () => {
    expect(isActive(null)).toBe(false)
    expect(isActive(status())).toBe(false)
    expect(isActive(status({ running: true }))).toBe(true)
    expect(isActive(status({ connecting: true }))).toBe(true)
  })
})

describe('shouldRefreshArticles', () => {
  it('pendant un lot et une dernière fois à sa fin', () => {
    expect(shouldRefreshArticles(null, status())).toBe(false)
    expect(shouldRefreshArticles(status(), status({ running: true }))).toBe(true)
    expect(shouldRefreshArticles(status({ running: true }), status({ running: true }))).toBe(true)
    expect(shouldRefreshArticles(status({ running: true }), status())).toBe(true)
    expect(shouldRefreshArticles(status(), status())).toBe(false)
  })

  it('pas pour une simple connexion', () => {
    expect(shouldRefreshArticles(status(), status({ connecting: true }))).toBe(false)
  })
})

describe('vintedBadge', () => {
  const sent = (vinted: Partial<VintedResult>) =>
    makeArticle('published', {
      vinted: {
        mode: 'draft',
        status: 'ok',
        missing_fields: [],
        url: 'https://www.vinted.fr/items/1',
        error: null,
        sent_at: '2026-10-11T10:00:00Z',
        ...vinted,
      },
    })

  it('aucun badge avant l’envoi', () => {
    expect(vintedBadge(makeArticle('validated'))).toBeNull()
  })

  it.each([
    [{ status: 'ok', mode: 'draft' }, 'Brouillon Vinted', 'info'],
    [{ status: 'ok', mode: 'publish' }, 'Publié sur Vinted', 'success'],
    [{ status: 'partial' }, 'À compléter sur Vinted', 'warn'],
    [{ status: 'error' }, 'Échec de l’envoi', 'danger'],
  ] as const)('%o → %s', (vinted, label, severity) => {
    const badge = vintedBadge(sent(vinted))
    expect(badge?.label).toBe(label)
    expect(badge?.severity).toBe(severity)
  })

  it('détail au survol', () => {
    expect(vintedBadge(sent({ status: 'partial', missing_fields: ['Marque', 'Taille'] }))?.detail)
      .toBe('À compléter : Marque, Taille')
    expect(vintedBadge(sent({ status: 'error', error: 'Vinted ne répond pas.' }))?.detail)
      .toBe('Vinted ne répond pas.')
  })
})

describe('sélection', () => {
  it('seuls les articles validés sont envoyables', () => {
    expect(sendable(makeArticle('validated'))).toBe(true)
    expect(sendable(makeArticle('to_review'))).toBe(false)
    expect(sendable(makeArticle('published'))).toBe(false)
  })

  it('retire de la sélection les articles qui ne sont plus validés', () => {
    const articles = [
      makeArticle('validated', { id: 'a' }),
      makeArticle('published', { id: 'b' }),
      makeArticle('validated', { id: 'c' }),
    ]
    expect(pruneSelection(['a', 'b', 'x', 'c'], articles)).toEqual(['a', 'c'])
  })
})
