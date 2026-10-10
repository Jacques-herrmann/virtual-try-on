<script setup lang="ts">
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import { computed, ref } from 'vue'

import { articleFile } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import { FILTERS, type FilterKey, matches } from '@/stores/articles'
import { type Article, label } from '@/types'

const props = defineProps<{ articles: Article[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string]; create: [] }>()

const filter = ref<FilterKey>('all')

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
    <p v-if="!visible.length" class="muted empty">Aucun article ici.</p>
    <button
      v-for="article in visible"
      :key="article.id"
      type="button"
      class="item"
      :class="{ selected: article.id === selectedId }"
      @click="emit('select', article.id)"
    >
      <img :src="articleFile(article, article.photos[0] ?? '')" alt="" class="thumb" />
      <span class="text">
        <span class="title">{{ article.listing?.title ?? label(article.input.garment_type) }}</span>
        <span class="muted small">
          {{ label(article.input.garment_type) }}
          <template v-if="article.input.brand"> · {{ article.input.brand }}</template>
          <template v-if="article.input.size"> · {{ article.input.size }}</template>
        </span>
      </span>
      <StatusTag :status="article.status" />
    </button>
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

.item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--p-border-radius-md);
  background: var(--p-surface-0);
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
</style>
