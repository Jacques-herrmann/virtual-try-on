<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useConfirm } from 'primevue/useconfirm'
import { computed, onMounted, ref } from 'vue'

import { api, articleFile } from '@/api'
import GalleryEditor from '@/components/GalleryEditor.vue'
import ListingForm from '@/components/ListingForm.vue'
import { useNotify } from '@/composables/notify'
import { useArticles } from '@/stores/articles'
import { useLicense } from '@/stores/license'
import { useScenes } from '@/stores/scenes'
import { useVinted } from '@/stores/vinted'
import type { Article, Listing } from '@/types'

/** `review` : tout est modifiable ; `validated` : lecture seule ; `error` : réessayer. */
const props = defineProps<{ article: Article; mode: 'review' | 'validated' | 'error' }>()

const { upsert, imageVersions } = useArticles()
const { nameOf } = useScenes()
const vinted = useVinted()
// Génération et envoi réservés aux abonnés ; relire, corriger et valider restent possibles.
const { licensed } = useLicense()
const notify = useNotify()
const confirm = useConfirm()

const working = ref<string | null>(null)
const listingForm = ref<InstanceType<typeof ListingForm> | null>(null)

const editable = computed(() => props.mode === 'review')
// L'ordre des photos reste modifiable jusqu'à l'envoi sur Vinted.
const galleryEditable = computed(
  () => props.mode === 'review' || props.article.status === 'validated',
)

onMounted(async () => {
  try {
    await vinted.loadCatalog()
  } catch {
    // catalogue indisponible : le formulaire le signale et reste utilisable
  }
})
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

const sent = computed(() => props.article.vinted)
const batchRunning = computed(() => !!vinted.status.value?.batch.running)

async function sendToVinted() {
  working.value = 'send'
  try {
    await vinted.send([id.value])
  } catch (e) {
    notify.error(e)
  } finally {
    working.value = null
  }
}

async function openOnVinted() {
  working.value = 'open'
  try {
    await vinted.open(id.value)
  } catch (e) {
    notify.error(e)
  } finally {
    working.value = null
  }
}

function saveGallery(gallery: string[] | null) {
  run('gallery', () => api.setGallery(id.value, gallery), 'Ordre des photos enregistré.')
}

// Enregistrement automatique depuis le formulaire : pas de message en cas de succès.
// L'identifiant est fixé à l'affichage : un enregistrement en attente au moment où l'on
// change d'article vise toujours l'article d'origine.
function listingSaver(articleId: string) {
  return async (listing: Listing) => {
    try {
      upsert(await api.updateListing(articleId, listing))
    } catch (e) {
      notify.error(e)
      throw e
    }
  }
}

async function validate() {
  await listingForm.value?.flush()
  if (listingForm.value?.dirty) {
    confirm.require({
      header: 'Annonce non enregistrée',
      message: 'Certaines modifications de l’annonce n’ont pas pu être enregistrées. Valider quand même (modifications perdues) ?',
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
          :disabled="!licensed"
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
              :disabled="!licensed"
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
        Aucune image retenue : ajoute une photo d'origine à l'annonce ci-dessous.
      </small>
    </section>

    <section v-if="galleryEditable" class="stack">
      <h3>Photos de l'annonce Vinted</h3>
      <GalleryEditor
        :article="article"
        :version="version"
        :saving="working === 'gallery'"
        @save="saveGallery"
      />
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
          :disabled="!licensed"
          @click="regenerateListing"
        />
      </div>
      <ListingForm
        :key="article.id"
        ref="listingForm"
        :listing="article.listing"
        :catalog="vinted.catalog.value"
        :readonly="!editable"
        :save="listingSaver(article.id)"
      />
    </section>

    <div v-if="mode === 'review'" class="footer row">
      <Button
        label="Valider l'article"
        icon="pi pi-check"
        :loading="working === 'validate'"
        @click="validate"
      />
    </div>

    <div v-else-if="mode === 'validated'" class="footer stack">
      <template v-if="article.status === 'published' && sent">
        <Message v-if="sent.status === 'partial'" severity="warn" :closable="false">
          Brouillon enregistré sur Vinted. À compléter sur Vinted :
          {{ sent.missing_fields.join(', ') }}.
        </Message>
        <Message v-else severity="success" :closable="false">
          {{ sent.mode === 'publish' ? 'Annonce publiée sur Vinted.' : 'Brouillon enregistré sur Vinted.' }}
        </Message>
        <div v-if="sent.url" class="row">
          <Button
            label="Ouvrir sur Vinted"
            icon="pi pi-external-link"
            :loading="working === 'open'"
            :disabled="batchRunning"
            @click="openOnVinted"
          />
        </div>
      </template>
      <template v-else>
        <Message v-if="sent?.status === 'error'" severity="error" :closable="false">
          Échec de l'envoi sur Vinted : {{ sent.error }}
        </Message>
        <div class="row">
          <Button
            :label="sent?.status === 'error' ? 'Réessayer' : 'Envoyer sur Vinted'"
            :icon="sent?.status === 'error' ? 'pi pi-refresh' : 'pi pi-send'"
            :loading="working === 'send'"
            :disabled="batchRunning || !licensed"
            @click="sendToVinted"
          />
          <Button
            label="Repasser en relecture"
            icon="pi pi-undo"
            severity="secondary"
            :loading="working === 'unvalidate'"
            :disabled="batchRunning"
            @click="run('unvalidate', () => api.unvalidate(id))"
          />
        </div>
      </template>
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
