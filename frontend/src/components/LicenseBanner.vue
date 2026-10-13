<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'

import { BLOCKED, useLicense } from '@/stores/license'

const CHECK_EVERY = 10 * 60 * 1000

const { license, load } = useLicense()
let timer: ReturnType<typeof setInterval> | undefined

const state = computed(() => license.value?.state)

async function refresh() {
  try {
    await load()
  } catch {
    // API injoignable : le bandeau « déconnecté » s'en charge.
  }
}

onMounted(() => {
  timer = setInterval(refresh, CHECK_EVERY)
})

onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div
    v-if="license && (state === 'expired' || state === 'unverified')"
    class="license-banner"
    :class="state"
    data-test="license-banner"
  >
    <template v-if="state === 'expired'">
      <strong>Ton abonnement est terminé.</strong>
      <span>{{ BLOCKED }} Tes articles restent consultables.</span>
      <a :href="`${license.site_url}/`" target="_blank" rel="noopener" data-test="renew">
        Renouveler
      </a>
    </template>
    <template v-else>
      <strong>
        {{ license.message ?? 'Impossible de vérifier ton abonnement. Vérifie ta connexion Internet.' }}
      </strong>
      <span>La génération et l'envoi sur Vinted reprendront dès la vérification.</span>
    </template>
  </div>
</template>

<style scoped>
.license-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.75rem;
  padding: 0.6rem 1rem;
  background: var(--p-amber-50);
  border-bottom: 1px solid var(--p-amber-200);
  color: var(--p-amber-900);
}

.license-banner.expired {
  background: var(--p-red-50);
  border-bottom-color: var(--p-red-200);
  color: var(--p-red-800);
}

a {
  color: inherit;
  font-weight: 600;
}
</style>
