<script setup lang="ts">
/** En-tête d'écran : titre, sous-titre et actions à droite. */
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <header class="page-header">
    <div class="text">
      <slot name="before" />
      <div class="title-row">
        <h1>{{ title }}</h1>
        <slot name="badge" />
      </div>
      <p v-if="subtitle || $slots.subtitle" class="subtitle muted">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem 1.5rem;
  flex-wrap: wrap;
}

.text {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.subtitle {
  margin: 0;
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
</style>
