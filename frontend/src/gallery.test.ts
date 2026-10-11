import { describe, expect, it } from 'vitest'

import { makeArticle } from '@/testing'
import type { SceneResult } from '@/types'

import { MAX_GALLERY, candidates, include, isCustom, move, remove } from './gallery'

function scene(name: string, changes: Partial<SceneResult> = {}): SceneResult {
  return {
    scene: name,
    status: 'ok',
    image: `generated/${name}.jpg`,
    error: null,
    excluded: false,
    ...changes,
  }
}

const article = makeArticle('to_review', {
  photos: ['photos/001.jpg', 'photos/002.jpg'],
  scenes: [
    scene('mannequin'),
    scene('cintre', { excluded: true }),
    scene('plage', { status: 'error', image: null, error: 'x' }),
    scene('pied'),
  ],
  effective_gallery: ['generated/mannequin.jpg', 'generated/pied.jpg'],
})

describe('candidates', () => {
  it('images retenues dans l’ordre des scènes, puis photos d’origine', () => {
    expect(candidates(article)).toEqual([
      'generated/mannequin.jpg',
      'generated/pied.jpg',
      'photos/001.jpg',
      'photos/002.jpg',
    ])
  })
})

describe('move', () => {
  const list = ['a', 'b', 'c', 'd']

  it.each([
    [0, 2, ['b', 'c', 'a', 'd']],
    [3, 0, ['d', 'a', 'b', 'c']],
    [1, 1, ['a', 'b', 'c', 'd']],
    [2, 9, ['a', 'b', 'd', 'c']],
  ])('%i → %i', (from, to, expected) => {
    expect(move(list, from, to)).toEqual(expected)
    expect(list).toEqual(['a', 'b', 'c', 'd'])
  })
})

describe('include / remove', () => {
  it('ajoute à la fin, sans doublon', () => {
    expect(include(['a'], 'b')).toEqual(['a', 'b'])
    expect(include(['a', 'b'], 'a')).toEqual(['a', 'b'])
  })

  it('refuse au-delà de 20 photos', () => {
    const full = Array.from({ length: MAX_GALLERY }, (_, i) => `p${i}`)
    expect(include(full, 'x')).toBe(full)
  })

  it('retire, mais jamais la dernière photo', () => {
    expect(remove(['a', 'b'], 'a')).toEqual(['b'])
    expect(remove(['a'], 'a')).toEqual(['a'])
  })
})

describe('isCustom', () => {
  it('l’ordre par défaut n’est pas un choix du vendeur', () => {
    expect(isCustom(article, ['generated/mannequin.jpg', 'generated/pied.jpg'])).toBe(false)
    expect(isCustom(article, ['generated/pied.jpg', 'generated/mannequin.jpg'])).toBe(true)
    expect(isCustom(article, ['generated/mannequin.jpg'])).toBe(true)
  })
})
