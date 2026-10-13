<script setup lang="ts">
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import { computed, ref } from 'vue'

import { api, articleFile } from '@/api'
import AppBanner from '@/components/ui/AppBanner.vue'
import { useNotify } from '@/composables/notify'
import { useArticles } from '@/stores/articles'
import { useScenes } from '@/stores/scenes'
import type { Article } from '@/types'

const props = defineProps<{ article: Article }>()

const { queue, upsert, imageVersions } = useArticles()
const { nameOf } = useScenes()
const notify = useNotify()
const cancelling = ref(false)

const running = computed(() => queue.value?.running === props.article.id)
const position = computed(() => {
  const i = queue.value?.pending.indexOf(props.article.id) ?? -1
  return i >= 0 ? i + 1 : null
})
const version = computed(() => imageVersions.value[props.article.id])

async function cancel() {
  cancelling.value = true
  try {
    upsert(await api.cancel(props.article.id))
  } catch (e) {
    notify.error(e)
  } finally {
    cancelling.value = false
  }
}
</script>

<template>
  <div class="progress">
    <AppBanner tone="brand" :icon="running ? 'icon-sparkles' : 'icon-clock'">
      <ProgressSpinner v-if="running" style="width: 20px; height: 20px" stroke-width="6" />
      <span v-if="running">
        <strong>Wearo prépare tes photos et ton annonce…</strong>
        Tu peux ajouter l'article suivant pendant ce temps.
      </span>
      <span v-else-if="position">En attente ({{ position }}ᵉ dans la file).</span>
      <span v-else>En attente…</span>
      <template #actions>
        <Button
          label="Annuler"
          severity="secondary"
          size="small"
          text
          :loading="cancelling"
          @click="cancel"
        />
      </template>
    </AppBanner>
    <div class="tiles surface">
      <figure class="tile">
        <img :src="articleFile(article, article.photos[0] ?? '')" alt="" />
        <figcaption>Photo d'origine</figcaption>
      </figure>
      <figure v-for="scene in article.scenes" :key="scene.scene" class="tile">
        <img
          v-if="scene.status === 'ok' && scene.image"
          :src="articleFile(article, scene.image, version)"
          alt=""
        />
        <div v-else-if="scene.status === 'error'" class="placeholder error">
          {{ scene.error }}
        </div>
        <div v-else class="placeholder pending" :aria-label="`${nameOf(scene.scene)} en préparation`">
          <i class="icon-sparkles" aria-hidden="true" />
        </div>
        <figcaption>{{ nameOf(scene.scene) }}</figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.progress {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 1rem;
  padding: 1.25rem;
}

.tile {
  margin: 0;
  min-width: 0;
}

.tile img,
.placeholder {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: 14px;
  background: var(--p-surface-100);
}

.placeholder {
  display: grid;
  place-items: center;
  color: var(--p-text-muted-color);
  padding: 0.75rem;
  text-align: center;
  font-size: 0.85rem;
}

.placeholder.pending {
  font-size: 1.75rem;
  color: var(--p-apricot-400);
  background: linear-gradient(
    110deg,
    var(--p-surface-100) 30%,
    var(--p-apricot-50) 50%,
    var(--p-surface-100) 70%
  );
  background-size: 250% 100%;
  animation: shimmer 1.6s linear infinite;
}

@keyframes shimmer {
  to {
    background-position: -150% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .placeholder.pending {
    animation: none;
  }
}

.placeholder.error {
  color: var(--p-red-700);
}

figcaption {
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: 0.4rem;
}
</style>
