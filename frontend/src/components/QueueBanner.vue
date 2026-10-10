<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import { ref } from 'vue'

import { api } from '@/api'
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
  <Message v-if="queue?.paused" severity="warn" :closable="false">
    <div class="stack">
      <span><strong>Génération en pause.</strong> {{ queue.reason }}</span>
      <div class="row">
        <Button label="Reprendre" size="small" :loading="resuming" @click="resume" />
        <RouterLink to="/settings" class="link">Ouvrir les réglages</RouterLink>
      </div>
    </div>
  </Message>
</template>

<style scoped>
.stack {
  gap: 0.5rem;
}

.link {
  font-size: 0.875rem;
}
</style>
