import { describe, expect, it } from 'vitest'

import type { VintedCatalog } from '@/types'

import { cascadeOptions, categoryPath, depth, isLeaf, sizesFor } from './catalog'

const catalog: VintedCatalog = {
  revision: 'r1',
  catalog: [
    {
      id: 1904,
      label: 'Femmes',
      children: [
        {
          id: 4,
          label: 'Vêtements',
          children: [
            { id: 1779, label: 'Robes', children: [], size_group: '4' },
            { id: 1781, label: 'Écharpes', children: [] },
          ],
        },
      ],
    },
    { id: 5, label: 'Hommes', children: [] },
  ],
  size_groups: { '4': ['XS', 'S', 'M'] },
  colors: ['Noir', 'Blanc'],
  conditions: ['Neuf', 'Bon état'],
  parcel_sizes: ['Petit'],
}

describe('cascadeOptions', () => {
  it('groupes avec `children`, feuilles avec une valeur et sans `children`', () => {
    expect(cascadeOptions(catalog.catalog)).toEqual([
      {
        label: 'Femmes',
        children: [
          {
            label: 'Vêtements',
            children: [
              { label: 'Robes', value: '1779' },
              { label: 'Écharpes', value: '1781' },
            ],
          },
        ],
      },
      { label: 'Hommes', value: '5' },
    ])
  })

  it('profondeur de l’arbre', () => {
    expect(depth(catalog.catalog)).toBe(3)
    expect(depth([])).toBe(0)
  })
})

describe('categoryPath / isLeaf', () => {
  it('chemin complet d’une catégorie', () => {
    expect(categoryPath(catalog, '1779')).toEqual(['Femmes', 'Vêtements', 'Robes'])
    expect(categoryPath(catalog, '5')).toEqual(['Hommes'])
    expect(categoryPath(catalog, '999')).toBeNull()
    expect(categoryPath(catalog, null)).toBeNull()
  })

  it('feuilles uniquement', () => {
    expect(isLeaf(catalog, '1779')).toBe(true)
    expect(isLeaf(catalog, '4')).toBe(false)
    expect(isLeaf(catalog, '999')).toBe(false)
  })
})

describe('sizesFor', () => {
  it('grille de la catégorie, vide sinon', () => {
    expect(sizesFor(catalog, '1779')).toEqual(['XS', 'S', 'M'])
    expect(sizesFor(catalog, '1781')).toEqual([])
    expect(sizesFor(catalog, null)).toEqual([])
    expect(sizesFor(null, '1779')).toEqual([])
  })
})
