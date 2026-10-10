import { createRouter, createWebHistory } from 'vue-router'

import { useSettings } from './stores/settings'

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
    { path: '/:rest(.*)*', redirect: '/articles' },
  ],
})

// Sans clé enregistrée, seul l'écran d'accueil est accessible.
router.beforeEach(async (to) => {
  const { settings, load } = useSettings()
  if (!settings.value) {
    try {
      await load()
    } catch {
      return true // API injoignable : le bandeau de déconnexion s'affiche
    }
  }
  const hasKey = settings.value?.has_key ?? false
  if (!hasKey && to.name !== 'welcome') return { name: 'welcome' }
  if (hasKey && to.name === 'welcome') return { name: 'articles' }
  return true
})
