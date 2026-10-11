<script setup lang="ts">
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { computed, ref, watch } from 'vue'

import { CONDITIONS, type Listing, PARCEL_SIZES } from '@/types'

const props = defineProps<{ listing: Listing; readonly?: boolean; saving?: boolean }>()
const emit = defineEmits<{ save: [listing: Listing] }>()

const draft = ref<Listing>({ ...props.listing })
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(props.listing))

// Après une régénération, l'annonce reçue remplace le brouillon s'il n'a pas été modifié.
watch(
  () => props.listing,
  (listing, previous) => {
    if (JSON.stringify(draft.value) === JSON.stringify(previous)) draft.value = { ...listing }
  },
)

defineExpose({ dirty })
</script>

<template>
  <form class="form" @submit.prevent="emit('save', draft)">
    <div class="field">
      <label for="title">Titre</label>
      <InputText id="title" v-model="draft.title" :disabled="readonly" fluid />
    </div>
    <div class="field">
      <label for="description">Description</label>
      <Textarea
        id="description"
        v-model="draft.description"
        rows="8"
        auto-resize
        :disabled="readonly"
        fluid
      />
    </div>
    <div class="grid">
      <div class="field">
        <label for="category">Catégorie</label>
        <InputText id="category" v-model="draft.category" :disabled="readonly" fluid />
      </div>
      <div class="field">
        <label for="lbrand">Marque</label>
        <InputText id="lbrand" v-model="draft.brand" :disabled="readonly" fluid />
      </div>
      <div class="field">
        <label for="lsize">Taille</label>
        <InputText id="lsize" v-model="draft.size" :disabled="readonly" fluid />
      </div>
      <div class="field">
        <label for="lcondition">État</label>
        <Select
          v-model="draft.condition"
          input-id="lcondition"
          :options="[...CONDITIONS]"
          show-clear
          :disabled="readonly"
          fluid
        />
      </div>
      <div class="field">
        <label for="lcolor">Couleur</label>
        <MultiSelect
          v-model="draft.color"
          input-id="lcolor"
          :options="draft.color"
          :selection-limit="2"
          :disabled="readonly"
          fluid
        />
      </div>
      <div class="field">
        <label for="lprice">Prix</label>
        <InputNumber
          v-model="draft.price"
          input-id="lprice"
          mode="currency"
          currency="EUR"
          locale="fr-FR"
          :min="0"
          :disabled="readonly"
          fluid
        />
      </div>
      <div class="field">
        <label for="parcel">Taille du colis</label>
        <Select
          v-model="draft.parcel_size"
          input-id="parcel"
          :options="[...PARCEL_SIZES]"
          show-clear
          :disabled="readonly"
          fluid
        />
      </div>
    </div>
    <div v-if="!readonly" class="row">
      <Button
        type="submit"
        label="Enregistrer l'annonce"
        icon="pi pi-save"
        :disabled="!dirty || !draft.title.trim()"
        :loading="saving"
      />
      <Button
        v-if="dirty"
        type="button"
        label="Annuler les modifications"
        severity="secondary"
        text
        @click="draft = { ...listing }"
      />
    </div>
  </form>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
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

label {
  font-size: 0.875rem;
  font-weight: 500;
}
</style>
