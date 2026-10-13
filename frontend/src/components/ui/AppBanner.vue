<script setup lang="ts">
import { computed } from 'vue'

/** Bandeau arrondi commun aux avertissements de licence, de mise à jour et de file. */
const props = defineProps<{ tone?: 'brand' | 'info' | 'warn' | 'danger'; icon?: string }>()

const DEFAULT_ICON = {
  brand: 'icon-sparkles',
  info: 'icon-info',
  warn: 'icon-triangle-alert',
  danger: 'icon-circle-alert',
} as const

const tone = computed(() => props.tone ?? 'info')
const icon = computed(() => props.icon ?? DEFAULT_ICON[tone.value])
</script>

<template>
  <div class="app-banner" :class="tone" role="status">
    <i :class="icon" class="lead" aria-hidden="true" />
    <div class="text"><slot /></div>
    <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped>
.app-banner {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  font-size: 0.95rem;
}

.lead {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.75rem;
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.brand {
  background: var(--p-apricot-100);
  color: var(--p-apricot-900);
}

.info {
  background: var(--p-sky-100);
  color: var(--p-sky-800);
}

.warn {
  background: var(--p-orange-100);
  color: var(--p-orange-800);
}

.danger {
  background: var(--p-red-100);
  color: var(--p-red-800);
}

.app-banner :deep(a) {
  color: inherit;
}
</style>
