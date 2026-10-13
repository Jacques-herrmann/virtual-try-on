<script setup lang="ts">
import ConfirmDialog from 'primevue/confirmdialog'
import Message from 'primevue/message'
import Toast from 'primevue/toast'
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { disconnected } from './api'
import LicenseBanner from './components/LicenseBanner.vue'
import UpdateBanner from './components/UpdateBanner.vue'

const route = useRoute()
const bare = computed(() => route.meta.bare === true)

const links = [
  { to: '/articles', label: 'Articles', icon: 'pi pi-images' },
  { to: '/scenes', label: 'Scènes', icon: 'pi pi-palette' },
  { to: '/settings', label: 'Réglages', icon: 'pi pi-cog' },
]
</script>

<template>
  <Toast position="bottom-right" />
  <ConfirmDialog />
  <Message v-if="disconnected" severity="error" :closable="false" class="disconnected">
    L'application ne répond plus. Ferme-la et relance-la.
  </Message>

  <RouterView v-if="bare" />
  <div v-else class="layout">
    <nav class="sidebar">
      <div class="brand">Virtual Try-On</div>
      <RouterLink v-for="link in links" :key="link.to" :to="link.to" class="nav-link">
        <i :class="link.icon" />
        <span>{{ link.label }}</span>
      </RouterLink>
    </nav>
    <div class="main">
      <LicenseBanner />
      <UpdateBanner />
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
  width: 190px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem 0.75rem;
  background: var(--p-surface-0);
  border-right: 1px solid var(--p-content-border-color);
}

.brand {
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--p-primary-700);
  padding: 0.25rem 0.75rem 1rem;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  border-radius: var(--p-border-radius-md);
  color: var(--p-text-color);
  text-decoration: none;
}

.nav-link:hover {
  background: var(--p-surface-100);
}

.nav-link.router-link-active {
  background: var(--p-primary-50);
  color: var(--p-primary-700);
  font-weight: 600;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
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
}
</style>
