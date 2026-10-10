<script setup lang="ts">
import Tag from 'primevue/tag'
import { computed } from 'vue'

import type { ArticleStatus } from '@/types'

const props = defineProps<{ status: ArticleStatus }>()

const LOOK: Record<ArticleStatus, { label: string; severity: string; icon?: string }> = {
  draft: { label: 'Brouillon', severity: 'secondary' },
  queued: { label: 'En attente', severity: 'info', icon: 'pi pi-clock' },
  generating: { label: 'En cours', severity: 'info', icon: 'pi pi-spin pi-spinner' },
  to_review: { label: 'À relire', severity: 'warn' },
  validated: { label: 'Validé', severity: 'success', icon: 'pi pi-check' },
  published: { label: 'Publié', severity: 'success' },
  error: { label: 'Erreur', severity: 'danger' },
}

const look = computed(() => LOOK[props.status])
</script>

<template>
  <Tag :value="look.label" :severity="look.severity" :icon="look.icon" rounded />
</template>
