<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ProgressBar from 'primevue/progressbar'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { api, ApiError } from '@/api'
import { useLicense } from '@/stores/license'
import type { UpdateProgress, UpdateSnapshot } from '@/types'

const CHECK_EVERY = 10 * 60 * 1000
const POLL_EVERY = 1000
// Page d'aide servie par le site de licence (le dépôt est privé).
const { license } = useLicense()
const helpUrl = computed(() => `${license.value?.site_url ?? ''}/aide`)

const snapshot = ref<UpdateSnapshot | null>(null)
const progress = ref<UpdateProgress | null>(null)
const error = ref<string | null>(null)
const starting = ref(false)
// Masqué jusqu'au prochain lancement de l'app (le composant vit aussi longtemps qu'elle).
const dismissed = ref(false)
const showNotes = ref(false)

let checkTimer: ReturnType<typeof setInterval> | undefined
let pollTimer: ReturnType<typeof setTimeout> | undefined

const required = computed(() => snapshot.value?.status === 'required')
const visible = computed(() => {
  const status = snapshot.value?.status
  if (status === 'required') return true
  return status === 'available' && !dismissed.value
})
const working = computed(
  () => starting.value || ['downloading', 'launching'].includes(progress.value?.state ?? ''),
)
const percent = computed(() => {
  const p = progress.value
  if (!p?.total) return null
  return Math.min(100, Math.round((p.received / p.total) * 100))
})

async function check() {
  try {
    snapshot.value = await api.update()
  } catch {
    // Pas de bandeau si l'API ne répond pas : le bandeau « déconnecté » s'en charge.
  }
}

async function poll() {
  try {
    progress.value = await api.updateProgress()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'La mise à jour a échoué.'
    return
  }
  const state = progress.value.state
  if (state === 'error') {
    error.value = progress.value.message
  } else if (state === 'downloading') {
    pollTimer = setTimeout(poll, POLL_EVERY)
  }
  // « launching » : l'app va se fermer, plus rien à interroger.
}

async function install() {
  error.value = null
  starting.value = true
  try {
    progress.value = await api.installUpdate()
    pollTimer = setTimeout(poll, POLL_EVERY)
  } catch (e) {
    progress.value = null
    error.value = e instanceof ApiError ? e.message : 'La mise à jour a échoué.'
  } finally {
    starting.value = false
  }
}

onMounted(() => {
  check()
  checkTimer = setInterval(check, CHECK_EVERY)
})

onUnmounted(() => {
  clearInterval(checkTimer)
  clearTimeout(pollTimer)
})
</script>

<template>
  <div v-if="visible && snapshot" class="update-banner" :class="{ required }">
    <div class="text">
      <strong v-if="required">
        Cette version ne fonctionne plus avec Vinted. Mets l'application à jour pour envoyer tes
        annonces.
      </strong>
      <strong v-else>Nouvelle version {{ snapshot.latest }} disponible.</strong>

      <template v-if="progress?.state === 'downloading'">
        <span>Téléchargement de la mise à jour…</span>
        <ProgressBar
          :value="percent ?? undefined"
          :mode="percent === null ? 'indeterminate' : 'determinate'"
          :show-value="false"
          class="bar"
        />
      </template>
      <span v-else-if="progress?.state === 'launching'">
        Installation… l'application va redémarrer.
      </span>
      <span v-else-if="!snapshot.can_install" class="hint">
        Mise à jour possible uniquement depuis l'application installée.
      </span>

      <span v-if="error" class="error">
        {{ error }}
        <a data-test="help" :href="helpUrl" target="_blank" rel="noopener">Aide</a>
      </span>
    </div>

    <div class="actions">
      <Button
        v-if="snapshot.notes"
        data-test="notes"
        label="Nouveautés"
        size="small"
        text
        @click="showNotes = true"
      />
      <Button
        v-if="!working"
        data-test="install"
        :label="error ? 'Réessayer' : 'Mettre à jour'"
        size="small"
        :severity="required ? 'danger' : undefined"
        :disabled="!snapshot.can_install"
        @click="install"
      />
      <Button
        v-if="!required && !working"
        data-test="dismiss"
        icon="pi pi-times"
        size="small"
        text
        rounded
        aria-label="Plus tard"
        @click="dismissed = true"
      />
    </div>

    <Dialog
      v-model:visible="showNotes"
      modal
      :header="`Nouveautés de la version ${snapshot.latest}`"
      :style="{ width: '32rem' }"
    >
      <p class="notes">{{ snapshot.notes }}</p>
    </Dialog>
  </div>
</template>

<style scoped>
.update-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 1rem;
  background: var(--p-primary-50);
  border-bottom: 1px solid var(--p-primary-200);
  color: var(--p-primary-800);
}

.update-banner.required {
  background: var(--p-red-50);
  border-bottom-color: var(--p-red-200);
  color: var(--p-red-800);
}

.text {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.75rem;
  min-width: 0;
}

.bar {
  width: 12rem;
  height: 0.5rem;
}

.hint {
  font-size: 0.875rem;
  opacity: 0.85;
}

.error {
  color: var(--p-red-700);
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.notes {
  white-space: pre-wrap;
  margin: 0;
}
</style>
