<script setup lang="ts">
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import SelectButton from 'primevue/selectbutton'
import { computed, ref, watch } from 'vue'

import { articleFile } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { deletable, FILTERS, type FilterKey, matches, pruneSelection } from '@/stores/articles'
import { useLicense } from '@/stores/license'
import { sendable } from '@/stores/vinted'
import { type Article, label } from '@/types'

const props = defineProps<{
  articles: Article[]
  selectedId: string | null
  /** Un envoi sur Vinted est en cours : pas de nouvel envoi. */
  sending?: boolean
}>()
const emit = defineEmits<{
  select: [id: string]
  send: [ids: string[]]
  delete: [ids: string[]]
}>()

const { licensed } = useLicense()
const filter = ref<FilterKey>('all')
const checked = ref<string[]>([])

const visible = computed(() => props.articles.filter((a) => matches(filter.value, a)))
const visibleIds = computed(() => visible.value.map((a) => a.id))
const allChecked = computed(
  () => visibleIds.value.length > 0 && visibleIds.value.every((id) => checked.value.includes(id)),
)
const checkedArticles = computed(() => props.articles.filter((a) => checked.value.includes(a.id)))
const toSend = computed(() => checkedArticles.value.filter(sendable).map((a) => a.id))
const toDelete = computed(() => checkedArticles.value.filter(deletable).map((a) => a.id))

watch(
  () => props.articles,
  (articles) => {
    checked.value = pruneSelection(checked.value, articles)
  },
)

function toggleAll() {
  const others = checked.value.filter((id) => !visibleIds.value.includes(id))
  checked.value = allChecked.value ? others : [...others, ...visibleIds.value]
}

function send() {
  emit('send', toSend.value)
  checked.value = []
}

function remove() {
  emit('delete', toDelete.value)
}

const options = computed(() =>
  FILTERS.map((f) => ({
    value: f.key,
    label: `${f.label} (${props.articles.filter((a) => matches(f.key, a)).length})`,
  })),
)


/** Vignette : première photo qui partira sur Vinted, sinon la photo d'origine. */
function thumbnail(article: Article): string {
  return articleFile(article, article.effective_gallery[0] ?? article.photos[0] ?? '')
}
</script>

<template>
  <div class="list">
    <div class="toolbar">
      <SelectButton
        v-model="filter"
        :options="options"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        class="filters"
        aria-label="Filtrer les articles"
      />
      <div v-if="visible.length" class="check-all">
        <Checkbox
          :model-value="allChecked"
          binary
          input-id="check-all"
          @update:model-value="toggleAll"
        />
        <label for="check-all">Tout sélectionner</label>
      </div>
    </div>

    <div v-if="checked.length" class="selection" data-test="selection-bar">
      <strong>{{ checked.length }} sélectionné{{ checked.length > 1 ? 's' : '' }}</strong>
      <span v-if="toSend.length < checked.length" class="muted hint">
        Seuls les articles validés et pas encore envoyés partent sur Vinted.
      </span>
      <span class="actions">
        <Button
          :label="`Envoyer sur Vinted (${toSend.length})`"
          icon="icon-send"
          size="small"
          :disabled="!toSend.length || sending || !licensed"
          @click="send"
        />
        <Button
          :label="`Supprimer (${toDelete.length})`"
          icon="icon-trash-2"
          size="small"
          severity="danger"
          outlined
          :disabled="!toDelete.length"
          @click="remove"
        />
        <Button
          label="Annuler"
          size="small"
          severity="secondary"
          text
          @click="checked = []"
        />
      </span>
    </div>

    <p v-if="!visible.length" class="muted empty">Aucun article ici.</p>
    <div v-else class="grid">
      <article
        v-for="article in visible"
        :key="article.id"
        class="card"
        :class="{ selected: article.id === selectedId, checked: checked.includes(article.id) }"
      >
        <button type="button" class="open" @click="emit('select', article.id)">
          <span class="thumb-wrap">
            <img :src="thumbnail(article)" alt="" class="thumb" loading="lazy" />
          </span>
          <span class="text">
            <span class="title">{{
              article.listing?.title ?? label(article.input.garment_type)
            }}</span>
            <span class="muted meta">
              {{ label(article.input.garment_type) }}
              <template v-if="article.input.brand"> · {{ article.input.brand }}</template>
              <template v-if="article.input.size"> · {{ article.input.size }}</template>
            </span>
            <span class="foot">
              <StatusTag :status="article.status" :article="article" class="tag" />
              <span v-if="article.listing?.price" class="price">{{ article.listing.price }} €</span>
            </span>
          </span>
        </button>
        <Checkbox
          v-model="checked"
          :value="article.id"
          class="pick"
          :aria-label="`Sélectionner ${article.listing?.title ?? label(article.input.garment_type)}`"
        />
      </article>
    </div>
  </div>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
}

.filters {
  flex-wrap: wrap;
}

.check-all {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.selection {
  position: sticky;
  top: 0.75rem;
  z-index: 2;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--w-radius-card);
  background: var(--p-apricot-50);
  border: 1px solid var(--p-apricot-200);
  box-shadow: var(--w-shadow-card);
}

.hint {
  font-size: 0.85rem;
}

.selection .actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-left: auto;
}

.empty {
  text-align: center;
  margin: 3rem 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
  gap: 1.125rem;
}

.card {
  position: relative;
  border-radius: var(--w-radius-card);
  background: var(--p-surface-0);
  border: 1px solid var(--p-surface-200);
  box-shadow: var(--w-shadow-card);
  overflow: hidden;
  transition:
    transform 0.15s,
    box-shadow 0.15s,
    border-color 0.15s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--w-shadow-raised);
}

.card.selected,
.card.checked {
  border-color: var(--p-apricot-400);
  box-shadow: 0 0 0 2px var(--p-apricot-200);
}

.open {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.thumb-wrap {
  display: block;
  aspect-ratio: 4 / 5;
  background: var(--p-surface-100);
}

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.75rem 0.875rem 0.875rem;
  min-width: 0;
}

.title {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta {
  font-size: 0.82rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.tag {
  font-size: 0.75rem;
  min-width: 0;
}

.price {
  font-weight: 700;
  color: var(--p-surface-700);
  white-space: nowrap;
}

.pick {
  position: absolute;
  top: 0.625rem;
  left: 0.625rem;
}

.pick :deep(.p-checkbox-box) {
  width: 1.4rem;
  height: 1.4rem;
  box-shadow: 0 1px 4px rgba(46, 31, 43, 0.25);
}
</style>
