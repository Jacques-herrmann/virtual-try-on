<script setup lang="ts">
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import SelectButton from 'primevue/selectbutton'
import { computed, ref, watch } from 'vue'

import { articleFile } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { FILTERS, type FilterKey, matches } from '@/stores/articles'
import { pruneSelection, sendable } from '@/stores/vinted'
import { type Article, label } from '@/types'

const props = defineProps<{
  articles: Article[]
  selectedId: string | null
  /** Un envoi sur Vinted est en cours : pas de nouvel envoi. */
  sending?: boolean
}>()
const emit = defineEmits<{ select: [id: string]; create: []; send: [ids: string[]] }>()

const filter = ref<FilterKey>('all')
const checked = ref<string[]>([])

const sendableIds = computed(() => props.articles.filter(sendable).map((a) => a.id))
const allChecked = computed(
  () => sendableIds.value.length > 0 && checked.value.length === sendableIds.value.length,
)

watch(
  () => props.articles,
  (articles) => {
    checked.value = pruneSelection(checked.value, articles)
  },
)

function toggleAll() {
  checked.value = allChecked.value ? [] : [...sendableIds.value]
}

function send() {
  emit('send', [...checked.value])
  checked.value = []
}

const options = computed(() =>
  FILTERS.map((f) => ({
    value: f.key,
    label: `${f.label} (${props.articles.filter((a) => matches(f.key, a)).length})`,
  })),
)

const visible = computed(() => props.articles.filter((a) => matches(filter.value, a)))
</script>

<template>
  <div class="list">
    <Button label="Nouvel article" icon="pi pi-plus" fluid @click="emit('create')" />
    <SelectButton
      v-model="filter"
      :options="options"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      size="small"
      class="filters"
    />
    <div v-if="sendableIds.length" class="send row">
      <Checkbox
        :model-value="allChecked"
        binary
        input-id="check-all"
        :disabled="sending"
        @update:model-value="toggleAll"
      />
      <label for="check-all" class="small">Validés</label>
      <span class="spacer" />
      <Button
        :label="`Envoyer sur Vinted (${checked.length})`"
        icon="pi pi-send"
        size="small"
        :disabled="!checked.length || sending"
        @click="send"
      />
    </div>
    <p v-if="!visible.length" class="muted empty">Aucun article ici.</p>
    <div
      v-for="article in visible"
      :key="article.id"
      class="item"
      :class="{ selected: article.id === selectedId }"
    >
      <Checkbox
        v-if="sendableIds.length"
        v-model="checked"
        :value="article.id"
        :disabled="!sendable(article) || sending"
        :class="{ hidden: !sendable(article) }"
        :aria-label="`Sélectionner pour l’envoi sur Vinted`"
      />
      <button type="button" class="open" @click="emit('select', article.id)">
        <img :src="articleFile(article, article.photos[0] ?? '')" alt="" class="thumb" />
        <span class="text">
          <span class="title">{{
            article.listing?.title ?? label(article.input.garment_type)
          }}</span>
          <span class="muted small">
            {{ label(article.input.garment_type) }}
            <template v-if="article.input.brand"> · {{ article.input.brand }}</template>
            <template v-if="article.input.size"> · {{ article.input.size }}</template>
          </span>
          <StatusTag :status="article.status" :article="article" class="tag" />
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filters {
  flex-wrap: wrap;
}

.filters :deep(.p-togglebutton) {
  flex: 1 1 auto;
  font-size: 0.8rem;
}

.empty {
  text-align: center;
  margin-top: 2rem;
}

.send {
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
}

.spacer {
  flex: 1;
}

.item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0 0 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--p-border-radius-md);
  background: var(--p-surface-0);
}

.hidden {
  visibility: hidden;
}

.open {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  min-width: 0;
  padding: 0.5rem 0.5rem 0.5rem 0;
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.item:hover {
  border-color: var(--p-surface-300);
}

.item.selected {
  border-color: var(--p-primary-400);
  background: var(--p-primary-50);
}

.thumb {
  width: 48px;
  height: 64px;
  object-fit: cover;
  border-radius: var(--p-border-radius-sm);
  background: var(--p-surface-100);
  flex-shrink: 0;
}

.text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.small {
  font-size: 0.8rem;
}

.tag {
  align-self: flex-start;
  margin-top: 0.25rem;
  font-size: 0.75rem;
}
</style>
