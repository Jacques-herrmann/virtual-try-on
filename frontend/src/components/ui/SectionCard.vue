<script setup lang="ts">
/** Carte titrée pour regrouper un réglage ou une partie de formulaire. */
defineProps<{ title?: string; subtitle?: string; icon?: string }>()
</script>

<template>
  <section class="section-card surface">
    <header v-if="title || $slots.header" class="head">
      <span v-if="icon" class="icon-badge" aria-hidden="true"><i :class="icon" /></span>
      <div class="titles">
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="subtitle" class="muted">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.header" class="extra"><slot name="header" /></div>
    </header>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.section-card {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.head {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
}

.icon-badge {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-apricot-50);
  color: var(--p-apricot-700);
  font-size: 1.2rem;
}

.titles {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.titles p {
  margin: 0;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
