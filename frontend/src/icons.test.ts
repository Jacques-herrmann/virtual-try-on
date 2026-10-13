// Chaque classe `icon-…` du code doit exister dans icons.css (généré par scripts/icons.mjs).
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { expect, it } from 'vitest'

const SRC = __dirname
const SPECIAL = new Set(['icon-spin', 'icon-badge'])

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return files(path)
    return /\.(vue|ts)$/.test(name) && !name.endsWith('.test.ts') ? [path] : []
  })
}

it('toutes les icônes utilisées sont générées', () => {
  const css = readFileSync(join(SRC, 'icons.css'), 'utf8')
  const defined = new Set([...css.matchAll(/\.(icon-[a-z0-9-]+)::before/g)].map((m) => m[1]))
  const used = new Set(
    files(SRC).flatMap((f) => [...readFileSync(f, 'utf8').matchAll(/\bicon-[a-z0-9-]+/g)].map((m) => m[0])),
  )
  const missing = [...used].filter((name) => !defined.has(name) && !SPECIAL.has(name))
  expect(missing, 'ajouter ces noms dans scripts/icons.mjs').toEqual([])
})
