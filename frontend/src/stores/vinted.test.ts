import { describe, expect, it } from 'vitest'

import type { VintedStatus } from '@/types'

import { isActive, shouldRefreshArticles } from './vinted'

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
