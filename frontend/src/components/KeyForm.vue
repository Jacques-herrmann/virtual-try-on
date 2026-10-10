<script setup lang="ts">
import Button from 'primevue/button'
import Password from 'primevue/password'
import { ref } from 'vue'

import { api, ApiError } from '@/api'
import { useSettings } from '@/stores/settings'
import type { SettingsView } from '@/types'

defineProps<{ cancellable?: boolean }>()
const emit = defineEmits<{ saved: [settings: SettingsView]; cancel: [] }>()

const key = ref('')
const checking = ref(false)
const error = ref<string | null>(null)
const { set } = useSettings()

async function verify() {
  checking.value = true
  error.value = null
  try {
    const settings = await api.checkKey(key.value)
    set(settings)
    key.value = ''
    emit('saved', settings)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Une erreur inattendue est survenue.'
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <form class="stack" @submit.prevent="verify">
    <label for="gemini-key">Clé API Gemini</label>
    <Password
      v-model="key"
      input-id="gemini-key"
      :feedback="false"
      toggle-mask
      fluid
      placeholder="AIza…"
      :invalid="!!error"
      :input-props="{ autocomplete: 'off' }"
    />
    <small v-if="error" class="error">{{ error }}</small>
    <div class="row">
      <Button
        type="submit"
        label="Vérifier"
        icon="pi pi-check"
        :loading="checking"
        :disabled="!key.trim()"
      />
      <Button
        v-if="cancellable"
        type="button"
        label="Annuler"
        severity="secondary"
        text
        @click="emit('cancel')"
      />
    </div>
  </form>
</template>

<style scoped>
.error {
  color: var(--p-red-600);
}
</style>
