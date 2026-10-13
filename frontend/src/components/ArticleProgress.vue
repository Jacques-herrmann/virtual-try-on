<script setup lang="ts">
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import { computed, ref } from 'vue'

import { api, articleFile } from '@/api'
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
  <div class="stack">
    <div class="row status">
      <ProgressSpinner v-if="running" style="width: 22px; height: 22px" stroke-width="6" />
      <span v-if="running">Génération en cours… Tu peux saisir l'article suivant pendant ce temps.</span>
      <span v-else-if="position">En attente ({{ position }}ᵉ dans la file).</span>
      <span v-else>En attente…</span>
      <Button
        label="Annuler"
        severity="secondary"
        size="small"
        text
        :loading="cancelling"
        @click="cancel"
      />
    </div>
    <div class="tiles">
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
        <div v-else class="placeholder"><i class="icon-clock" /></div>
        <figcaption>{{ nameOf(scene.scene) }}</figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.status {
  min-height: 2.25rem;
}

.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.tile {
  margin: 0;
  width: 180px;
}

.tile img,
.placeholder {
  width: 180px;
  height: 240px;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
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

.placeholder.error {
  color: var(--p-red-600);
}

figcaption {
  font-size: 0.85rem;
  margin-top: 0.25rem;
  color: var(--p-text-muted-color);
}
</style>
