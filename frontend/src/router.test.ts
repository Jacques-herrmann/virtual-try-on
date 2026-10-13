import { describe, expect, it, vi } from 'vitest'

import type { LicenseSnapshot, LicenseState } from './types'

vi.mock('./views/WelcomeView.vue', () => ({ default: {} }))
vi.mock('./views/ArticlesView.vue', () => ({ default: {} }))
vi.mock('./views/ScenesView.vue', () => ({ default: {} }))
vi.mock('./views/SettingsView.vue', () => ({ default: {} }))

const { needsWelcome } = await import('./router')

function license(state: LicenseState): LicenseSnapshot {
  return {
    state,
    key_hint: null,
    status: null,
    period_end: null,
    devices_max: 2,
    message: null,
    site_url: 'https://licence.test',
  }
}

describe('needsWelcome', () => {
  it("garde l'accueil tant qu'il n'y a pas de licence", () => {
    expect(needsWelcome(true, license('none'))).toBe(true)
    expect(needsWelcome(true, null)).toBe(true)
  })

  it("garde l'accueil tant qu'il n'y a pas de clé Gemini", () => {
    expect(needsWelcome(false, license('active'))).toBe(true)
  })

  it.each(['active', 'expired', 'unverified'] as const)(
    "ouvre l'application avec une licence %s et une clé Gemini",
    (state) => {
      expect(needsWelcome(true, license(state))).toBe(false)
    },
  )
})
