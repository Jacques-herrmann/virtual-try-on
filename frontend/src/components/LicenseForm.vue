<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { ref } from 'vue'

import { api, ApiError } from '@/api'
import { useLicense } from '@/stores/license'
import type { LicenseSnapshot } from '@/types'

defineProps<{ cancellable?: boolean }>()
const emit = defineEmits<{ saved: [license: LicenseSnapshot]; cancel: [] }>()

const key = ref('')
const checking = ref(false)
const error = ref<string | null>(null)
const { set } = useLicense()

async function activate() {
  checking.value = true
  error.value = null
  try {
    const license = await api.activateLicense(key.value)
    set(license)
    key.value = ''
    emit('saved', license)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Une erreur inattendue est survenue.'
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <form class="stack" @submit.prevent="activate">
    <label for="license-key">Clé de licence</label>
    <InputText
      id="license-key"
      v-model="key"
      fluid
      placeholder="VTO-XXXX-XXXX-XXXX-XXXX"
      autocomplete="off"
      spellcheck="false"
      :invalid="!!error"
    />
    <small v-if="error" class="error" data-test="license-error">{{ error }}</small>
    <div class="row">
      <Button
        type="submit"
        label="Activer"
        icon="icon-check"
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
