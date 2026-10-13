<script setup lang="ts">
import Button from 'primevue/button'
import { ref } from 'vue'

import { api } from '@/api'
import AppBanner from '@/components/ui/AppBanner.vue'
import { useNotify } from '@/composables/notify'
import { useArticles } from '@/stores/articles'

const { queue, refresh, startPolling } = useArticles()
const notify = useNotify()
const resuming = ref(false)

async function resume() {
  resuming.value = true
  try {
    queue.value = await api.resumeQueue()
    await refresh()
    startPolling()
  } catch (e) {
    notify.error(e)
  } finally {
    resuming.value = false
  }
}
</script>

<template>
  <AppBanner v-if="queue?.paused" tone="warn" icon="icon-clock">
    <span><strong>Génération en pause.</strong> {{ queue.reason }}</span>
    <RouterLink to="/settings">Ouvrir les réglages</RouterLink>
    <template #actions>
      <Button label="Reprendre" size="small" :loading="resuming" @click="resume" />
    </template>
  </AppBanner>
</template>
