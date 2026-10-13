<script setup lang="ts">
import CascadeSelect from 'primevue/cascadeselect'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { cascadeOptions, categoryPath, depth, isLeaf, sameSize, sizesFor } from '@/catalog'
import { CONDITIONS, type Listing, PARCEL_SIZES, type VintedCatalog } from '@/types'

const props = defineProps<{
  listing: Listing
  /** Catalogue Vinted ; null s'il n'est pas (encore) disponible. */
  catalog: VintedCatalog | null
  readonly?: boolean
  /** Enregistre l'annonce ; rejette en cas d'échec (l'appelant a déjà prévenu le vendeur). */
  save: (listing: Listing) => Promise<void>
}>()

/** Délai après la dernière modification avant l'enregistrement automatique. */
const AUTOSAVE_MS = 800

function copy(listing: Listing): Listing {
  return { ...listing, color: [...(listing.color ?? [])] }
}

const draft = ref<Listing>(copy(props.listing))
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(props.listing))

// Après une régénération, l'annonce reçue remplace le brouillon s'il n'a pas été modifié.
watch(
  () => props.listing,
  (listing, previous) => {
    if (JSON.stringify(draft.value) === JSON.stringify(previous)) draft.value = copy(listing)
  },
)

const categories = computed(() => (props.catalog ? cascadeOptions(props.catalog.catalog) : []))
// PrimeVue lit `optionGroupChildren` niveau par niveau : un nom par niveau de l'arbre.
const childrenKeys = computed(() =>
  Array<string>(props.catalog ? depth(props.catalog.catalog) : 1).fill('children'),
)
const path = computed(() => categoryPath(props.catalog, draft.value.category)?.join(' › '))
const unknownCategory = computed(
  () => !!props.catalog && !!draft.value.category && !isLeaf(props.catalog, draft.value.category),
)

const sizes = computed(() => sizesFor(props.catalog, draft.value.category))
// Sans catégorie choisie, la taille reste libre ; une catégorie sans grille n'a pas de taille.
const showSize = computed(() => !draft.value.category || sizes.value.length > 0)
const sizeOutOfGrid = computed(
  () =>
    sizes.value.length > 0 &&
    !!draft.value.size &&
    !sizes.value.some((s) => sameSize(s, draft.value.size)),
)
// Taille équivalente mais écrite autrement (espaces) : affichée telle quelle dans la liste.
const sizeNotExact = computed(() => !!draft.value.size && !sizes.value.includes(draft.value.size))

const colors = computed(() => {
  const known = props.catalog?.colors ?? []
  return [...known, ...draft.value.color.filter((c) => !known.includes(c))]
})
const unknownColors = computed(() =>
  props.catalog ? draft.value.color.filter((c) => !props.catalog!.colors.includes(c)) : [],
)

const conditions = computed(() => props.catalog?.conditions ?? [...CONDITIONS])
const parcelSizes = computed(() => props.catalog?.parcel_sizes ?? [...PARCEL_SIZES])

// Une annonce sans titre ou avec une catégorie inconnue n'est pas enregistrée.
const invalidReason = computed(() => {
  if (!draft.value.title.trim()) return 'le titre est vide'
  if (unknownCategory.value) return 'choisis une catégorie Vinted'
  return null
})

const status = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
let timer: ReturnType<typeof setTimeout> | undefined
let inflight: Promise<void> | null = null

watch(
  draft,
  () => {
    clearTimeout(timer)
    if (!props.readonly && dirty.value) timer = setTimeout(() => void flush(), AUTOSAVE_MS)
  },
  { deep: true },
)

/** Enregistre tout de suite les modifications en attente (une seule requête à la fois). */
async function flush(): Promise<void> {
  clearTimeout(timer)
  while (inflight) await inflight
  if (props.readonly || !dirty.value || invalidReason.value) return
  status.value = 'saving'
  inflight = props
    .save(copy(draft.value))
    .then(
      () => {
        status.value = 'saved'
      },
      () => {
        status.value = 'error'
      },
    )
    .finally(() => {
      inflight = null
    })
  await inflight
}

// Changement d'article ou d'écran : rien n'est perdu.
onBeforeUnmount(() => void flush())

defineExpose({ dirty, flush })
</script>

<template>
  <form class="form" @submit.prevent="flush()">
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
    <div class="field">
      <label for="category">Catégorie Vinted</label>
      <CascadeSelect
        v-model="draft.category"
        input-id="category"
        :options="categories"
        option-label="label"
        option-value="value"
        option-group-label="label"
        :option-group-children="childrenKeys"
        placeholder="Choisir une catégorie"
        :disabled="readonly || !catalog"
        fluid
      >
        <template #value="{ value, placeholder }">
          <span v-if="value">{{ path ?? 'Catégorie inconnue' }}</span>
          <span v-else class="muted">{{ placeholder }}</span>
        </template>
      </CascadeSelect>
      <small v-if="!catalog" class="muted">
        Liste des catégories Vinted indisponible pour le moment.
      </small>
      <small v-else-if="unknownCategory" class="warn">
        Cette catégorie n’existe plus sur Vinted : choisis-en une autre.
      </small>
    </div>
    <div class="grid">
      <div class="field">
        <label for="lbrand">Marque</label>
        <InputText id="lbrand" v-model="draft.brand" :disabled="readonly" fluid />
      </div>
      <div v-if="showSize" class="field">
        <label for="lsize">Taille</label>
        <Select
          v-if="sizes.length"
          v-model="draft.size"
          input-id="lsize"
          :options="sizes"
          show-clear
          :placeholder="sizeNotExact ? draft.size ?? undefined : undefined"
          :disabled="readonly"
          fluid
        />
        <InputText v-else id="lsize" v-model="draft.size" :disabled="readonly" fluid />
        <small v-if="sizeOutOfGrid" class="warn">
          « {{ draft.size }} » n’existe pas pour cette catégorie sur Vinted.
        </small>
      </div>
      <div class="field">
        <label for="lcondition">État</label>
        <Select
          v-model="draft.condition"
          input-id="lcondition"
          :options="conditions"
          show-clear
          :disabled="readonly"
          fluid
        />
      </div>
      <div class="field">
        <label for="lcolor">Couleurs (2 au plus)</label>
        <MultiSelect
          v-model="draft.color"
          input-id="lcolor"
          :options="colors"
          :selection-limit="2"
          :show-toggle-all="false"
          display="chip"
          filter
          :disabled="readonly"
          fluid
        />
        <small v-if="unknownColors.length" class="warn">
          Couleur inconnue sur Vinted : {{ unknownColors.join(', ') }}.
        </small>
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
          :options="parcelSizes"
          show-clear
          :disabled="readonly"
          fluid
        />
      </div>
    </div>
    <div v-if="!readonly" class="autosave">
      <small v-if="status === 'saving'" class="muted">
        <i class="icon-loader-circle icon-spin" /> Enregistrement…
      </small>
      <small v-else-if="dirty && invalidReason" class="warn">
        Modifications non enregistrées : {{ invalidReason }}.
      </small>
      <small v-else-if="status === 'error'" class="warn">
        L’annonce n’a pas pu être enregistrée.
        <a href="#" @click.prevent="flush()">Réessayer</a>
      </small>
      <small v-else-if="status === 'saved' && !dirty" class="muted">
        <i class="icon-check" /> Modifications enregistrées
      </small>
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

.autosave {
  min-height: 1.25rem;
}

.warn {
  color: var(--p-orange-600);
}
</style>
