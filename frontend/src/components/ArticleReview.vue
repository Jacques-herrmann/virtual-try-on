<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useConfirm } from 'primevue/useconfirm'
import { computed, ref } from 'vue'

import { api, articleFile } from '@/api'
import ListingForm from '@/components/ListingForm.vue'
import { useNotify } from '@/composables/notify'
import { useArticles } from '@/stores/articles'
import { useScenes } from '@/stores/scenes'
import type { Article, Listing } from '@/types'

/** `review` : tout est modifiable ; `validated` : lecture seule ; `error` : réessayer. */
const props = defineProps<{ article: Article; mode: 'review' | 'validated' | 'error' }>()

const { upsert, imageVersions } = useArticles()
const { nameOf } = useScenes()
const notify = useNotify()
const confirm = useConfirm()

const working = ref<string | null>(null)
const listingForm = ref<InstanceType<typeof ListingForm> | null>(null)

const editable = computed(() => props.mode === 'review')
const version = computed(() => imageVersions.value[props.article.id])
const keptImages = computed(
  () => props.article.scenes.filter((s) => s.status === 'ok' && !s.excluded).length,
)

async function run(key: string, action: () => Promise<Article>, success?: string) {
  working.value = key
  try {
    upsert(await action())
    if (success) notify.success(success)
  } catch (e) {
    notify.error(e)
  } finally {
    working.value = null
  }
}

const id = computed(() => props.article.id)

function regenerateScene(scene: string) {
  run(`scene:${scene}`, () => api.generate(id.value, { scenes: [scene] }))
}

function toggleExcluded(scene: string, excluded: boolean) {
  run(`exclude:${scene}`, () => api.setExcluded(id.value, scene, excluded))
}

function regenerateAll() {
  confirm.require({
    header: 'Tout régénérer ?',
    message: 'Toutes les images et l’annonce seront refaites. Tes modifications de l’annonce seront perdues.',
    accept: () => run('all', () => api.generate(id.value)),
  })
}

function regenerateListing() {
  confirm.require({
    header: 'Régénérer l’annonce ?',
    message: 'Le texte actuel de l’annonce sera remplacé.',
    accept: () => run('listing', () => api.generate(id.value, { listing: true })),
  })
}

function saveListing(listing: Listing) {
  run('save', () => api.updateListing(id.value, listing), 'Annonce enregistrée.')
}

function validate() {
  if (listingForm.value?.dirty) {
    confirm.require({
      header: 'Annonce non enregistrée',
      message: 'Tu as modifié l’annonce sans l’enregistrer. Valider quand même (modifications perdues) ?',
      accept: () => run('validate', () => api.validate(id.value), 'Article validé.'),
    })
    return
  }
  run('validate', () => api.validate(id.value), 'Article validé.')
}
</script>

<template>
  <div class="review">
    <Message v-if="mode === 'error'" severity="error" :closable="false">
      {{ article.error ?? 'La génération a échoué.' }}
    </Message>

    <section class="stack">
      <div class="row between">
        <h3>Images</h3>
        <Button
          v-if="mode !== 'validated'"
          :label="mode === 'error' ? 'Réessayer' : 'Tout régénérer'"
          icon="pi pi-refresh"
          severity="secondary"
          size="small"
          :loading="working === 'all'"
          @click="mode === 'error' ? run('all', () => api.generate(id)) : regenerateAll()"
        />
      </div>
      <div class="tiles">
        <figure class="tile">
          <img :src="articleFile(article, article.photos[0] ?? '')" alt="" />
          <figcaption>Photo d'origine</figcaption>
        </figure>
        <figure
          v-for="scene in article.scenes"
          :key="scene.scene"
          class="tile"
          :class="{ excluded: scene.excluded }"
        >
          <div class="frame">
            <img
              v-if="scene.status === 'ok' && scene.image"
              :src="articleFile(article, scene.image, version)"
              alt=""
            />
            <div v-else class="placeholder">{{ scene.error ?? 'Pas d’image' }}</div>
            <span v-if="scene.excluded" class="badge">Écartée</span>
          </div>
          <figcaption>{{ nameOf(scene.scene) }}</figcaption>
          <div v-if="editable" class="row actions">
            <Button
              icon="pi pi-refresh"
              label="Régénérer"
              size="small"
              text
              :loading="working === `scene:${scene.scene}`"
              @click="regenerateScene(scene.scene)"
            />
            <Button
              v-if="scene.status === 'ok'"
              :icon="scene.excluded ? 'pi pi-eye' : 'pi pi-eye-slash'"
              :label="scene.excluded ? 'Reprendre' : 'Écarter'"
              size="small"
              text
              severity="secondary"
              :loading="working === `exclude:${scene.scene}`"
              @click="toggleExcluded(scene.scene, !scene.excluded)"
            />
          </div>
        </figure>
      </div>
      <small v-if="editable && keptImages === 0" class="warn">
        Aucune image retenue : seule la photo d'origine partira sur Vinted.
      </small>
    </section>

    <section v-if="article.listing" class="stack">
      <div class="row between">
        <h3>Annonce</h3>
        <Button
          v-if="editable"
          label="Régénérer l'annonce"
          icon="pi pi-refresh"
          severity="secondary"
          size="small"
          :loading="working === 'listing'"
          @click="regenerateListing"
        />
      </div>
      <ListingForm
        :key="article.id"
        ref="listingForm"
        :listing="article.listing"
        :readonly="!editable"
        :saving="working === 'save'"
        @save="saveListing"
      />
    </section>

    <div v-if="mode !== 'error'" class="footer row">
      <Button
        v-if="mode === 'review'"
        label="Valider l'article"
        icon="pi pi-check"
        :loading="working === 'validate'"
        @click="validate"
      />
      <Button
        v-if="mode === 'validated'"
        label="Repasser en relecture"
        icon="pi pi-undo"
        severity="secondary"
        :loading="working === 'unvalidate'"
        @click="run('unvalidate', () => api.unvalidate(id))"
      />
      <span v-if="mode === 'validated'" class="muted">
        Prêt pour Vinted (l'envoi arrive dans une prochaine version).
      </span>
    </div>
  </div>
</template>

<style scoped>
.review {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.between {
  justify-content: space-between;
}

.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.tile {
  margin: 0;
  width: 200px;
}

.frame {
  position: relative;
}

.tile img,
.placeholder {
  display: block;
  width: 200px;
  height: 266px;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
  background: var(--p-surface-100);
}

.placeholder {
  display: grid;
  place-items: center;
  padding: 0.75rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--p-red-600);
}

.tile.excluded img {
  opacity: 0.35;
  filter: grayscale(1);
}

.badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 0.75rem;
  padding: 0.15rem 0.45rem;
  border-radius: var(--p-border-radius-sm);
  background: var(--p-surface-700);
  color: white;
}

figcaption {
  font-size: 0.85rem;
  margin-top: 0.25rem;
  color: var(--p-text-muted-color);
}

.actions {
  gap: 0;
  flex-wrap: wrap;
}

.warn {
  color: var(--p-orange-600);
}

.footer {
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-content-border-color);
}
</style>
