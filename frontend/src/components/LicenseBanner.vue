<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'

import { api } from '@/api'
import AppBanner from '@/components/ui/AppBanner.vue'
import { useNotify } from '@/composables/notify'
import { BLOCKED, useLicense } from '@/stores/license'

const CHECK_EVERY = 10 * 60 * 1000

const { license, load } = useLicense()
const notify = useNotify()
let timer: ReturnType<typeof setInterval> | undefined

const state = computed(() => license.value?.state)

async function refresh() {
  try {
    await load()
  } catch {
    // API injoignable : le bandeau « déconnecté » s'en charge.
  }
}

async function renew() {
  try {
    const { url } = await api.licenseRenew()
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    notify.error(e)
  }
}

onMounted(() => {
  timer = setInterval(refresh, CHECK_EVERY)
})

onUnmounted(() => clearInterval(timer))
</script>

<template>
  <AppBanner
    v-if="license && (state === 'expired' || state === 'unverified')"
    :tone="state === 'expired' ? 'danger' : 'warn'"
    :icon="state === 'expired' ? 'icon-credit-card' : 'icon-wifi-off'"
    :class="state"
    data-test="license-banner"
  >
    <template v-if="state === 'expired'">
      <strong>Ton abonnement est terminé.</strong>
      <span>{{ BLOCKED }} Tes articles restent consultables.</span>
    </template>
    <template v-else>
      <strong>
        {{ license.message ?? 'Impossible de vérifier ton abonnement. Vérifie ta connexion Internet.' }}
      </strong>
      <span>La génération et l'envoi sur Vinted reprendront dès la vérification.</span>
    </template>
    <template v-if="state === 'expired'" #actions>
      <a href="#" class="renew" data-test="renew" @click.prevent="renew">Renouveler</a>
    </template>
  </AppBanner>
</template>

<style scoped>
.renew {
  font-weight: 700;
  white-space: nowrap;
}
</style>
