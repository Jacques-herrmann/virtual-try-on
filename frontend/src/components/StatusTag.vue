<script setup lang="ts">
import Tag from 'primevue/tag'
import { computed } from 'vue'

import { vintedBadge } from '@/stores/vinted'
import type { Article, ArticleStatus } from '@/types'

/** Avec `article`, le résultat de l'envoi sur Vinted remplace le statut s'il existe. */
const props = defineProps<{ status: ArticleStatus; article?: Article }>()

const LOOK: Record<ArticleStatus, { label: string; severity: string; icon?: string }> = {
  draft: { label: 'Brouillon', severity: 'secondary' },
  queued: { label: 'En attente', severity: 'info', icon: 'icon-clock' },
  generating: { label: 'En cours', severity: 'info', icon: 'icon-loader-circle icon-spin' },
  to_review: { label: 'À relire', severity: 'warn' },
  validated: { label: 'Validé', severity: 'success', icon: 'icon-check' },
  published: { label: 'Publié', severity: 'success' },
  error: { label: 'Erreur', severity: 'danger' },
}

const look = computed(
  () => (props.article && vintedBadge(props.article)) || { ...LOOK[props.status], detail: undefined },
)
</script>

<template>
  <Tag
    :value="look.label"
    :severity="look.severity"
    :icon="look.icon"
    :title="look.detail"
    rounded
  />
</template>
