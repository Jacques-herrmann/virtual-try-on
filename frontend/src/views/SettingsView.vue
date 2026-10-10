<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Panel from 'primevue/panel'
import Textarea from 'primevue/textarea'
import { useConfirm } from 'primevue/useconfirm'
import { onMounted, ref } from 'vue'

import { api } from '@/api'
import KeyForm from '@/components/KeyForm.vue'
import { useNotify } from '@/composables/notify'
import { useSettings } from '@/stores/settings'

const { settings, load, set } = useSettings()
const notify = useNotify()
const confirm = useConfirm()

const changingKey = ref(false)
const signature = ref('')
const listingPrompt = ref('')
const imageModel = ref('')
const textModel = ref('')
const saving = ref(false)

function fill() {
  if (!settings.value) return
  signature.value = settings.value.signature
  listingPrompt.value = settings.value.listing_prompt
  imageModel.value = settings.value.image_model
  textModel.value = settings.value.text_model
}

onMounted(async () => {
  try {
    await load()
    fill()
  } catch (e) {
    notify.error(e)
  }
})

async function save(changes: Parameters<typeof api.updateSettings>[0]) {
  saving.value = true
  try {
    set(await api.updateSettings(changes))
    fill()
    notify.success('Réglages enregistrés.')
  } catch (e) {
    notify.error(e)
  } finally {
    saving.value = false
  }
}

function resetPrompt() {
  confirm.require({
    header: 'Rétablir le texte par défaut ?',
    message: 'Tes modifications des consignes d’annonce seront perdues.',
    accept: async () => {
      try {
        set(await api.resetListingPrompt())
        fill()
        notify.success('Texte par défaut rétabli.')
      } catch (e) {
        notify.error(e)
      }
    },
  })
}

async function openLogs() {
  try {
    await api.openLogs()
  } catch (e) {
    notify.error(e)
  }
}

function keySaved() {
  changingKey.value = false
  notify.success('Clé vérifiée et enregistrée.')
}
</script>

<template>
  <div class="page stack">
    <h1>Réglages</h1>

    <Panel header="Clé Gemini">
      <div v-if="!changingKey" class="row">
        <span>Clé enregistrée : <code>••••{{ settings?.key_hint }}</code></span>
        <Button label="Changer" severity="secondary" size="small" @click="changingKey = true" />
      </div>
      <KeyForm v-else cancellable @saved="keySaved" @cancel="changingKey = false" />
    </Panel>

    <Panel header="Annonces">
      <div class="stack">
        <label for="signature">Signature ajoutée à la fin de chaque description</label>
        <Textarea id="signature" v-model="signature" rows="3" auto-resize fluid />
        <label for="listing-prompt">Consignes données à l’IA pour rédiger l’annonce</label>
        <Textarea id="listing-prompt" v-model="listingPrompt" rows="14" fluid class="mono" />
        <div class="row">
          <Button
            label="Enregistrer"
            icon="pi pi-save"
            :loading="saving"
            @click="save({ signature, listing_prompt: listingPrompt })"
          />
          <Button
            label="Rétablir le texte par défaut"
            severity="secondary"
            text
            @click="resetPrompt"
          />
        </div>
      </div>
    </Panel>

    <Panel header="Avancé" toggleable collapsed>
      <div class="stack">
        <p class="muted">Modèles Gemini utilisés. Ne change ces valeurs que si on te le demande.</p>
        <label for="image-model">Modèle pour les images</label>
        <InputText id="image-model" v-model="imageModel" fluid />
        <label for="text-model">Modèle pour les annonces</label>
        <InputText id="text-model" v-model="textModel" fluid />
        <div>
          <Button
            label="Enregistrer"
            icon="pi pi-save"
            :loading="saving"
            @click="save({ image_model: imageModel, text_model: textModel })"
          />
        </div>
      </div>
    </Panel>

    <Panel header="Assistance">
      <div class="row">
        <Button
          label="Ouvrir le dossier des logs"
          icon="pi pi-folder-open"
          severity="secondary"
          @click="openLogs"
        />
        <span class="muted">À joindre à ta demande si quelque chose ne fonctionne pas.</span>
      </div>
    </Panel>
  </div>
</template>

<style scoped>
.page {
  max-width: 820px;
  padding: 1.5rem 2rem 3rem;
  gap: 1.25rem;
}

.mono {
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
}
</style>
