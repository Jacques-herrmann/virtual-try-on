<script setup lang="ts">
/** État vide illustré : un cintre dessiné, un titre, un texte et une action. */
defineProps<{ title: string; text?: string; compact?: boolean }>()
</script>

<template>
  <div class="empty-state" :class="{ compact }">
    <svg class="illustration" viewBox="0 0 160 120" aria-hidden="true">
      <circle cx="80" cy="64" r="52" fill="var(--p-apricot-50)" />
      <path
        d="M74 40c0-6 3-10 8-10s8 3 7.5 7.5c-.5 3.5-4 5-9.5 8.5L42 72c-2.5 1.6-1.4 5 1.4 5h73.2c2.8 0 3.9-3.4 1.4-5L80 46"
        fill="none"
        stroke="var(--p-apricot-500)"
        stroke-width="5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M122 22q1.5 9 10 10.5-8.5 1.5-10 10.5-1.5-9-10-10.5 8.5-1.5 10-10.5Z"
        fill="var(--p-apricot-300)"
      />
      <path d="M36 30q1 5.5 6 6.5-5 1-6 6.5-1-5.5-6-6.5 5-1 6-6.5Z" fill="var(--p-apricot-200)" />
    </svg>
    <h2>{{ title }}</h2>
    <p v-if="text" class="muted">{{ text }}</p>
    <div v-if="$slots.default" class="actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.5rem;
  padding: 3rem 1.5rem;
  max-width: 28rem;
  margin: 0 auto;
}

.empty-state.compact {
  padding: 1.5rem 1rem;
}

.illustration {
  width: 160px;
  height: 120px;
  margin-bottom: 0.5rem;
}

.compact .illustration {
  width: 112px;
  height: 84px;
}

p {
  margin: 0;
}

.actions {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
}
</style>
