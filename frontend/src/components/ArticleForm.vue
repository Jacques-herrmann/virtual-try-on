<script setup lang="ts">
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Textarea from 'primevue/textarea'
import { computed, reactive, ref } from 'vue'

import PhotoDrop from '@/components/PhotoDrop.vue'
import { useAutoTour } from '@/composables/tour'
import { BLOCKED } from '@/stores/license'
import { AUDIENCES, CONDITIONS, GARMENT_TYPES, label, type UserInput } from '@/types'

/** `create` : photos + « Générer » ; `edit` : correction de la saisie d'un article existant. */
const props = defineProps<{
  mode: 'create' | 'edit'
  initial?: UserInput
  busy?: boolean
  /** Création refusée (pas d'abonnement actif) : le bouton « Générer » est désactivé. */
  locked?: boolean
}>()
const emit = defineEmits<{ submit: [input: UserInput, photos: File[]]; cancel: [] }>()

useAutoTour('article-form', () => props.mode === 'create')

const input = reactive<UserInput>({
  garment_type: props.initial?.garment_type ?? (undefined as unknown as UserInput['garment_type']),
  audience: props.initial?.audience ?? null,
  brand: props.initial?.brand ?? null,
  size: props.initial?.size ?? null,
  condition: props.initial?.condition ?? null,
  color: props.initial?.color ?? null,
  price: props.initial?.price ?? null,
  notes: props.initial?.notes ?? null,
})
const photos = ref<File[]>([])

const typeOptions = GARMENT_TYPES.map((t) => ({ value: t, label: label(t) }))
const audienceOptions = AUDIENCES.map((a) => ({ value: a, label: label(a) }))

// Le public choisit les décors des scènes et la branche du catalogue Vinted.
const canSubmit = computed(
  () =>
    !!input.garment_type &&
    !!input.audience &&
    (props.mode === 'edit' || photos.value.length > 0),
)

function clean(value: string | null | undefined) {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

function submit() {
  if (!canSubmit.value) return
  emit(
    'submit',
    {
      ...input,
      brand: clean(input.brand),
      size: clean(input.size),
      color: clean(input.color),
      notes: clean(input.notes),
    },
    photos.value,
  )
}
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <PhotoDrop
      v-if="mode === 'create'"
      v-model="photos"
      data-tour="photos"
      hint="La première photo sert de référence : vêtement bien visible, à plat ou sur cintre."
    />

    <div class="grid">
      <div class="field" data-tour="garment-type">
        <label for="type">Type de vêtement *</label>
        <Select
          v-model="input.garment_type"
          input-id="type"
          :options="typeOptions"
          option-label="label"
          option-value="value"
          placeholder="Choisir…"
          fluid
        />
      </div>
      <div class="field">
        <label>Pour *</label>
        <SelectButton
          v-model="input.audience"
          :options="audienceOptions"
          option-label="label"
          option-value="value"
        />
      </div>
      <div class="field" data-tour="optional-fields">
        <label for="brand">Marque</label>
        <InputText id="brand" v-model="input.brand" fluid />
      </div>
      <div class="field">
        <label for="size">Taille</label>
        <InputText id="size" v-model="input.size" placeholder="M, 38, 10 ans…" fluid />
      </div>
      <div class="field">
        <label for="condition">État</label>
        <Select
          v-model="input.condition"
          input-id="condition"
          :options="[...CONDITIONS]"
          placeholder="Laisser l'IA proposer"
          show-clear
          fluid
        />
      </div>
      <div class="field">
        <label for="color">Couleur</label>
        <InputText id="color" v-model="input.color" fluid />
      </div>
      <div class="field">
        <label for="price">Prix</label>
        <InputNumber
          v-model="input.price"
          input-id="price"
          mode="currency"
          currency="EUR"
          locale="fr-FR"
          :min="0"
          placeholder="Laisser l'IA proposer"
          fluid
        />
      </div>
      <div class="field wide">
        <label for="notes">Remarques (défaut, matière, coupe…)</label>
        <Textarea id="notes" v-model="input.notes" style="--rows: 2" fluid />
      </div>
    </div>

    <div class="row">
      <Button
        type="submit"
        data-tour="generate"
        :label="mode === 'create' ? 'Générer' : 'Enregistrer'"
        :icon="mode === 'create' ? 'icon-sparkles' : 'icon-save'"
        :disabled="!canSubmit || (mode === 'create' && locked)"
        :loading="busy"
      />
      <Button
        v-if="mode === 'edit'"
        type="button"
        label="Annuler"
        severity="secondary"
        text
        @click="emit('cancel')"
      />
      <small v-if="mode === 'create' && locked" class="muted" data-test="locked">
        {{ BLOCKED }}
      </small>
      <small v-else-if="mode === 'create' && !canSubmit" class="muted">
        Ajoute au moins une photo, choisis le type et pour qui est le vêtement.
      </small>
      <small v-else-if="mode === 'edit' && !canSubmit" class="muted">
        Choisis le type et pour qui est le vêtement.
      </small>
    </div>
  </form>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field.wide {
  grid-column: 1 / -1;
}

label {
  font-size: 0.875rem;
  font-weight: 500;
}
</style>
