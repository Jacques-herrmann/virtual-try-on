<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import { computed, ref, watch } from 'vue'

import { useNotify } from '@/composables/notify'
import { useVinted } from '@/stores/vinted'
import type { Article } from '@/types'

const props = defineProps<{ articles: Article[] }>()

const { status, stop } = useVinted()
const notify = useNotify()
const stopping = ref(false)
const dismissed = ref<string | null>(null)

const batch = computed(() => status.value?.batch ?? null)
const percent = computed(() =>
  batch.value?.total ? Math.round((batch.value.done / batch.value.total) * 100) : 0,
)
const current = computed(() => {
  const article = props.articles.find((a) => a.id === batch.value?.current)
  return article?.listing?.title ?? null
})
const message = computed(() => {
  const text = batch.value?.message
  return text && text !== dismissed.value && !batch.value?.running ? text : null
})

// Un nouveau lot fait réapparaître son éventuel message de fin.
watch(
  () => batch.value?.running,
  (running) => {
    if (running) {
      dismissed.value = null
      stopping.value = false
    }
  },
)

async function stopBatch() {
  stopping.value = true
  try {
    await stop()
  } catch (e) {
    stopping.value = false
    notify.error(e)
  }
}
</script>

<template>
  <Message v-if="batch?.running" severity="info" :closable="false">
    <div class="stack">
      <strong>Envoi sur Vinted : {{ batch.done }} / {{ batch.total }}</strong>
      <ProgressBar :value="percent" :show-value="false" class="bar" />
      <span v-if="batch.paused_reason === 'login_required'" class="warn">
        Connecte-toi à Vinted dans la fenêtre qui vient de s’ouvrir : l’envoi reprendra tout
        seul.
      </span>
      <span v-else-if="current" class="small">En cours : {{ current }}</span>
      <span v-if="stopping" class="small muted">Arrêt après l’article en cours…</span>
      <div>
        <Button
          label="Arrêter"
          icon="pi pi-stop-circle"
          severity="secondary"
          size="small"
          :disabled="stopping"
          @click="stopBatch"
        />
      </div>
    </div>
  </Message>
  <Message v-else-if="message" severity="warn" closable @close="dismissed = message">
    {{ message }}
  </Message>
</template>

<style scoped>
.stack {
  gap: 0.5rem;
}

.bar {
  height: 0.4rem;
}

.small {
  font-size: 0.85rem;
}

.warn {
  font-size: 0.85rem;
  color: var(--p-orange-700);
}
</style>
