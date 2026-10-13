<script setup lang="ts">
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { api, disconnected } from './api'
import LicenseBanner from './components/LicenseBanner.vue'
import AppBanner from './components/ui/AppBanner.vue'
import AppLogo from './components/ui/AppLogo.vue'
import UpdateBanner from './components/UpdateBanner.vue'
import { formatDate, useLicense } from './stores/license'

const route = useRoute()
const bare = computed(() => route.meta.bare === true)
const { license } = useLicense()

const links = [
  { to: '/articles', label: 'Articles', icon: 'icon-shirt' },
  { to: '/scenes', label: 'Scènes', icon: 'icon-image' },
  { to: '/settings', label: 'Réglages', icon: 'icon-settings' },
]

const version = ref<string | null>(null)
const trialEnd = computed(() =>
  license.value?.status === 'trialing' ? formatDate(license.value.period_end) : null,
)

onMounted(async () => {
  try {
    version.value = (await api.update()).current
  } catch {
    // Version absente du pied de page : sans gravité.
  }
})
</script>

<template>
  <Toast position="bottom-right" />
  <ConfirmDialog />
  <AppBanner v-if="disconnected" tone="danger" icon="icon-wifi-off" class="disconnected">
    <strong>Kaloé ne répond plus.</strong> Ferme l'application et relance-la.
  </AppBanner>

  <RouterView v-if="bare" />
  <div v-else class="layout">
    <nav class="sidebar" aria-label="Navigation principale">
      <RouterLink to="/articles" class="brand" aria-label="Kaloé, mes articles">
        <AppLogo :height="30" />
      </RouterLink>
      <RouterLink v-for="link in links" :key="link.to" :to="link.to" class="nav-link">
        <i :class="link.icon" aria-hidden="true" />
        <span>{{ link.label }}</span>
      </RouterLink>

      <div class="spacer" />
      <RouterLink v-if="trialEnd" to="/settings" class="trial" data-test="trial-card">
        <strong>Essai gratuit</strong>
        <span>jusqu'au {{ trialEnd }}</span>
      </RouterLink>
      <div v-if="version" class="version">Kaloé {{ version }}</div>
    </nav>
    <div class="main">
      <div class="banners">
        <LicenseBanner />
        <UpdateBanner />
      </div>
      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 1.5rem 1rem 1.25rem;
  background: var(--p-surface-100);
}

.brand {
  padding: 0.25rem 0.75rem 1.5rem;
  align-self: flex-start;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 2.75rem;
  padding: 0 0.875rem;
  border-radius: 12px;
  color: var(--p-surface-700);
  font-weight: 600;
  text-decoration: none;
  transition: background 0.15s;
}

.nav-link i {
  font-size: 1.2rem;
}

.nav-link:hover {
  background: color-mix(in srgb, var(--p-surface-0), transparent 40%);
  color: var(--p-text-color);
}

.nav-link.router-link-active {
  background: var(--p-surface-0);
  color: var(--p-text-color);
  font-weight: 700;
  box-shadow: 0 1px 2px rgba(46, 31, 43, 0.08);
}

.nav-link.router-link-active i {
  color: var(--p-apricot-600);
}

.spacer {
  flex: 1;
}

.trial {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.75rem 0.875rem;
  border-radius: 14px;
  background: var(--p-surface-0);
  color: var(--p-text-color);
  text-decoration: none;
  font-weight: 400;
  font-size: 0.85rem;
}

.trial span {
  color: var(--p-text-muted-color);
}

.version {
  padding: 0.5rem 0.875rem 0;
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.banners {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 var(--w-gutter);
}

.banners:has(> *) {
  padding-top: 1.25rem;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.disconnected {
  position: fixed;
  top: 0.75rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  box-shadow: var(--w-shadow-raised);
}
</style>
