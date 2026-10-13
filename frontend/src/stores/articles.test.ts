import { afterEach, describe, expect, it, vi } from 'vitest'

import { makeArticle as article } from '@/testing'

import { createPoller, deletable, isBusy, matches, panelFor, pruneSelection } from './articles'

describe('panelFor', () => {
  it.each([
    [null, 'form'],
    ['draft', 'draft'],
    ['queued', 'progress'],
    ['generating', 'progress'],
    ['to_review', 'review'],
    ['validated', 'validated'],
    ['published', 'validated'],
    ['error', 'error'],
  ] as const)('%s → %s', (status, panel) => {
    expect(panelFor(status ? article(status) : null)).toBe(panel)
  })
})

describe('isBusy / matches', () => {
  it('détecte les articles en attente ou en cours', () => {
    expect(isBusy([article('to_review'), article('validated')])).toBe(false)
    expect(isBusy([article('to_review'), article('queued')])).toBe(true)
    expect(isBusy([article('generating')])).toBe(true)
  })

  it('filtre par statut', () => {
    expect(matches('all', article('draft'))).toBe(true)
    expect(matches('busy', article('generating'))).toBe(true)
    expect(matches('busy', article('to_review'))).toBe(false)
    expect(matches('validated', article('published'))).toBe(true)
  })
})

describe('sélection', () => {
  it('un article en cours de génération ne peut pas être supprimé', () => {
    expect(deletable(article('to_review'))).toBe(true)
    expect(deletable(article('published'))).toBe(true)
    expect(deletable(article('queued'))).toBe(false)
    expect(deletable(article('generating'))).toBe(false)
  })

  it('retire de la sélection les articles disparus', () => {
    const articles = [article('validated', { id: 'a' }), article('to_review', { id: 'b' })]
    expect(pruneSelection(['a', 'x', 'b'], articles)).toEqual(['a', 'b'])
  })
})

describe('createPoller', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('interroge tant que des articles sont en cours, puis s’arrête', async () => {
    vi.useFakeTimers()
    let remaining = 2
    const tick = vi.fn(async () => {
      remaining -= 1
    })
    const poller = createPoller(tick, () => remaining > 0, 1500)

    poller.start()
    expect(tick).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1500)
    expect(tick).toHaveBeenCalledTimes(1)
    expect(poller.running).toBe(true)
    await vi.advanceTimersByTimeAsync(1500)
    expect(tick).toHaveBeenCalledTimes(2)
    expect(poller.running).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(tick).toHaveBeenCalledTimes(2)
  })

  it('reprend après un nouvel appel à start, sans doubler la boucle', async () => {
    vi.useFakeTimers()
    let busy = false
    const tick = vi.fn(async () => {})
    const poller = createPoller(tick, () => busy, 1000)

    poller.start()
    await vi.advanceTimersByTimeAsync(1000)
    expect(poller.running).toBe(false)

    busy = true
    poller.start()
    poller.start()
    await vi.advanceTimersByTimeAsync(1000)
    expect(tick).toHaveBeenCalledTimes(2)
    poller.stop()
    await vi.advanceTimersByTimeAsync(3000)
    expect(tick).toHaveBeenCalledTimes(2)
  })

  it('continue malgré une erreur ponctuelle', async () => {
    vi.useFakeTimers()
    const tick = vi.fn().mockRejectedValueOnce(new Error('réseau')).mockResolvedValue(undefined)
    const poller = createPoller(tick, () => true, 1000)
    poller.start()
    await vi.advanceTimersByTimeAsync(2000)
    expect(tick).toHaveBeenCalledTimes(2)
    poller.stop()
  })
})
