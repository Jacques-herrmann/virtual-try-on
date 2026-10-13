import { createRouter, createWebHistory } from 'vue-router'

import { useLicense } from './stores/license'
import { useSettings } from './stores/settings'
import type { LicenseSnapshot } from './types'

/** L'accueil guide la saisie de la clé de licence puis de la clé Gemini. */
export function needsWelcome(hasGeminiKey: boolean, license: LicenseSnapshot | null): boolean {
  return !hasGeminiKey || (license?.state ?? 'none') === 'none'
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/articles' },
    {
      path: '/welcome',
      name: 'welcome',
      component: () => import('./views/WelcomeView.vue'),
      meta: { bare: true },
    },
    { path: '/articles/:id?', name: 'articles', component: () => import('./views/ArticlesView.vue') },
    { path: '/scenes/:slug?', name: 'scenes', component: () => import('./views/ScenesView.vue') },
    { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
    { path: '/aide', name: 'help', component: () => import('./views/HelpView.vue') },
    { path: '/:rest(.*)*', redirect: '/articles' },
  ],
})

// Sans clé de licence ou sans clé Gemini, seul l'écran d'accueil est accessible.
router.beforeEach(async (to) => {
  const { settings, load } = useSettings()
  const { license, load: loadLicense } = useLicense()
  try {
    await Promise.all([
      settings.value ? null : load(),
      license.value ? null : loadLicense(),
    ])
  } catch {
    return true // API injoignable : le bandeau de déconnexion s'affiche
  }
  const welcome = needsWelcome(settings.value?.has_key ?? false, license.value)
  if (welcome && to.name !== 'welcome') return { name: 'welcome' }
  if (!welcome && to.name === 'welcome') return { name: 'articles' }
  return true
})
