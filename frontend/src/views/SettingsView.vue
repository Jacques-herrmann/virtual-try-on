<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import SelectButton from 'primevue/selectbutton'
import Textarea from 'primevue/textarea'
import { useConfirm } from 'primevue/useconfirm'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import KeyForm from '@/components/KeyForm.vue'
import LicenseSection from '@/components/LicenseSection.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useNotify } from '@/composables/notify'
import { useSettings } from '@/stores/settings'
import { useVinted } from '@/stores/vinted'
import type { VintedMode, VintedStatus } from '@/types'

const { settings, load, set } = useSettings()
const showAdvanced = ref(false)
const vinted = useVinted()
const notify = useNotify()
const confirm = useConfirm()

const changingKey = ref(false)
const signature = ref('')
const listingPrompt = ref('')
const imageModel = ref('')
const textModel = ref('')
const saving = ref(false)
const vintedWorking = ref(false)

const MODES: { label: string; value: VintedMode }[] = [
  { label: 'Enregistrer en brouillon', value: 'draft' },
  { label: 'Publier directement', value: 'publish' },
]

const SOURCES: Record<NonNullable<VintedStatus['data_source']>, string> = {
  remote: 'à jour',
  cache: 'copie enregistrée sur cet ordinateur',
  bundled: 'version livrée avec l’application',
}

const isBusyVinted = computed(
  () => !!vinted.status.value?.connecting || !!vinted.status.value?.batch.running,
)

const connection = computed(() => {
  const status = vinted.status.value
  if (status?.connecting) return 'Connecte-toi dans la fenêtre Vinted qui vient de s’ouvrir…'
  if (status?.connected === true) return 'Ton compte Vinted est connecté.'
  if (status?.connected === false) return 'Ton compte Vinted n’est pas connecté.'
  return 'Connexion pas encore vérifiée.'
})

const dataInfo = computed(() => {
  const status = vinted.status.value
  if (!status?.data_revision || !status.data_source) return 'Données Vinted indisponibles.'
  return `Données Vinted : révision ${status.data_revision} (${SOURCES[status.data_source]}).`
})

function fill() {
  if (!settings.value) return
  signature.value = settings.value.signature
  listingPrompt.value = settings.value.listing_prompt
  imageModel.value = settings.value.image_model
  textModel.value = settings.value.text_model
}

onMounted(async () => {
  try {
    await Promise.all([load(), vinted.load()])
    fill()
  } catch (e) {
    notify.error(e)
  }
})

async function vintedAction(action: () => Promise<void>) {
  vintedWorking.value = true
  try {
    await action()
  } catch (e) {
    notify.error(e)
  } finally {
    vintedWorking.value = false
  }
}

function disconnectVinted() {
  confirm.require({
    header: 'Déconnecter ton compte Vinted ?',
    message:
      'La fenêtre Vinted de l’application oubliera ta connexion. Il faudra te reconnecter avant le prochain envoi.',
    acceptProps: { label: 'Déconnecter', severity: 'danger' },
    rejectProps: { label: 'Annuler', severity: 'secondary', text: true },
    accept: () => vintedAction(vinted.disconnect),
  })
}

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
    <PageHeader title="Réglages" subtitle="Ton abonnement, ta clé Gemini, tes annonces et ta connexion Vinted." />

    <SectionCard title="Abonnement" icon="icon-credit-card">
      <LicenseSection />
    </SectionCard>

    <SectionCard
      title="Clé Gemini"
      subtitle="L’IA de Google qui crée tes photos et tes annonces."
      icon="icon-key-round"
    >
      <div v-if="!changingKey" class="row">
        <span>Clé enregistrée : <code>••••{{ settings?.key_hint }}</code></span>
        <Button label="Changer" severity="secondary" size="small" @click="changingKey = true" />
      </div>
      <KeyForm v-else cancellable @saved="keySaved" @cancel="changingKey = false" />
    </SectionCard>

    <SectionCard
      title="Annonces"
      subtitle="Ce que l’IA écrit, et ce que Wearo ajoute à chaque description."
      icon="icon-pencil"
    >
      <div class="stack">
        <label for="signature">Signature ajoutée à la fin de chaque description</label>
        <Textarea id="signature" v-model="signature" rows="3" auto-resize fluid />
        <label for="listing-prompt">Consignes données à l’IA pour rédiger l’annonce</label>
        <Textarea id="listing-prompt" v-model="listingPrompt" rows="14" fluid class="mono" />
        <div class="row">
          <Button
            label="Enregistrer"
            icon="icon-save"
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
    </SectionCard>

    <SectionCard title="Vinted" icon="icon-send">
      <div class="stack">
        <div class="row">
          <i v-if="vinted.status.value?.connecting" class="icon-loader-circle icon-spin" />
          <span>{{ connection }}</span>
        </div>
        <p class="muted">
          L’application ouvre sa propre fenêtre Vinted. Tu t’y connectes une seule fois ; ton
          mot de passe n’est jamais enregistré par l’application.
        </p>
        <div class="row">
          <Button
            label="Connecter mon compte"
            icon="icon-log-in"
            :loading="vintedWorking || !!vinted.status.value?.connecting"
            :disabled="!!vinted.status.value?.batch.running"
            @click="vintedAction(vinted.connect)"
          />
          <Button
            label="Déconnecter"
            icon="icon-log-out"
            severity="secondary"
            text
            :disabled="vintedWorking || isBusyVinted"
            @click="disconnectVinted"
          />
        </div>
        <label for="vinted-mode">Après le remplissage de l’annonce</label>
        <SelectButton
          id="vinted-mode"
          :model-value="settings?.vinted_mode"
          :options="MODES"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          :disabled="saving"
          @update:model-value="(mode: VintedMode) => save({ vinted_mode: mode })"
        />
        <small class="muted">Une annonce incomplète est toujours enregistrée en brouillon.</small>
        <small class="muted">{{ dataInfo }}</small>
      </div>
    </SectionCard>

    <SectionCard title="Avancé" icon="icon-settings">
      <template #header>
        <Button
          :label="showAdvanced ? 'Masquer' : 'Afficher'"
          severity="secondary"
          size="small"
          text
          @click="showAdvanced = !showAdvanced"
        />
      </template>
      <div v-if="showAdvanced" class="stack">
        <p class="muted">Modèles Gemini utilisés. Ne change ces valeurs que si on te le demande.</p>
        <label for="image-model">Modèle pour les images</label>
        <InputText id="image-model" v-model="imageModel" fluid />
        <label for="text-model">Modèle pour les annonces</label>
        <InputText id="text-model" v-model="textModel" fluid />
        <div>
          <Button
            label="Enregistrer"
            icon="icon-save"
            :loading="saving"
            @click="save({ image_model: imageModel, text_model: textModel })"
          />
        </div>
      </div>
    </SectionCard>

    <SectionCard title="Assistance" icon="icon-info">
      <div class="row">
        <Button
          label="Ouvrir le dossier des logs"
          icon="icon-folder-open"
          severity="secondary"
          @click="openLogs"
        />
        <span class="muted">À joindre à ta demande si quelque chose ne fonctionne pas.</span>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  padding: 1.75rem var(--w-gutter) 3rem;
  gap: 1.25rem;
}

label {
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
}
</style>
