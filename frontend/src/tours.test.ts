import { describe, expect, it } from 'vitest'

import { TOURS } from './tours'

// Sources des composants : une refonte qui retire un data-tour casserait la visite sans bruit.
const sources = Object.values(
  import.meta.glob('./**/*.vue', { query: '?raw', import: 'default', eager: true }),
) as string[]
const declared = new Set(
  sources.flatMap((source) => [
    ...[...source.matchAll(/data-tour="([^"]+)"/g)].map((m) => m[1]),
    ...[...source.matchAll(/tour: '([^']+)'/g)].map((m) => m[1]), // liens de la barre latérale
  ]),
)

describe('TOURS', () => {
  it.each(Object.entries(TOURS))('chaque étape de « %s » vise un data-tour existant', (_, steps) => {
    for (const step of steps) {
      const name = /^\[data-tour="([^"]+)"\]$/.exec(step.target)?.[1]
      expect(name, step.target).toBeTruthy()
      expect(declared, `data-tour="${name}" introuvable`).toContain(name)
    }
  })
})
