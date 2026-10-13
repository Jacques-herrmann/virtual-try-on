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

    <div class="columns">
      <div class="col">
        <section class="panel surface stack">
          <div class="row between">
            <h2>Photos</h2>
            <Button
              v-if="mode !== 'validated'"
              :label="mode === 'error' ? 'Réessayer' : 'Tout régénérer'"
              icon="icon-refresh-cw"
              severity="secondary"
              size="small"
              :loading="working === 'all'"
              :disabled="!licensed"
              @click="mode === 'error' ? run('all', () => api.generate(id)) : regenerateAll()"
            />
          </div>
          <div class="tiles">
            <figure class="tile">
              <div class="frame">
                <img :src="articleFile(article, article.photos[0] ?? '')" alt="" />
              </div>
              <figcaption>Photo d'origine</figcaption>
            </figure>
            <figure
              v-for="scene in article.scenes"
              :key="scene.scene"
              class="tile"
              :class="{ excluded: scene.excluded, kept: scene.status === 'ok' && !scene.excluded }"
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
              <div v-if="editable" class="actions">
                <Button
                  icon="icon-refresh-cw"
                  label="Régénérer"
                  size="small"
                  text
                  :loading="working === `scene:${scene.scene}`"
                  :disabled="!licensed"
                  @click="regenerateScene(scene.scene)"
                />
                <Button
                  v-if="scene.status === 'ok'"
                  :icon="scene.excluded ? 'icon-eye' : 'icon-eye-off'"
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

        <section v-if="galleryEditable" class="panel surface stack">
          <div class="stack tight">
            <h2>Photos de l'annonce Vinted</h2>
            <p class="muted">L'ordre ci-dessous est celui de l'annonce ; la première sert de couverture.</p>
          </div>
          <GalleryEditor
            :article="article"
            :version="version"
            :saving="working === 'gallery'"
            @save="saveGallery"
          />
        </section>
      </div>

      <section v-if="article.listing" class="panel surface stack col">
        <div class="row between">
          <h2>Annonce</h2>
          <Button
            v-if="editable"
            label="Régénérer l'annonce"
            icon="icon-refresh-cw"
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
    </div>

    <div v-if="mode === 'review'" class="action-bar">
      <i class="icon-circle-check lead" aria-hidden="true" />
      <span class="hint">
        {{ keptImages }} photo{{ keptImages > 1 ? 's' : '' }} retenue{{ keptImages > 1 ? 's' : '' }}.
        Rien ne part sur Vinted sans ta validation.
      </span>
      <Button
        label="Valider l'article"
        icon="icon-check"
        :loading="working === 'validate'"
        @click="validate"
      />
    </div>

    <div v-else-if="mode === 'validated'" class="action-bar">
      <template v-if="article.status === 'published' && sent">
        <Message v-if="sent.status === 'partial'" severity="warn" :closable="false" class="grow">
          Brouillon enregistré sur Vinted. À compléter sur Vinted :
          {{ sent.missing_fields.join(', ') }}.
        </Message>
        <Message v-else severity="success" :closable="false" class="grow">
          {{ sent.mode === 'publish' ? 'Annonce publiée sur Vinted.' : 'Brouillon enregistré sur Vinted.' }}
        </Message>
        <Button
          v-if="sent.url"
          label="Ouvrir sur Vinted"
          icon="icon-external-link"
          :loading="working === 'open'"
          :disabled="batchRunning"
          @click="openOnVinted"
        />
      </template>
      <template v-else>
        <Message v-if="sent?.status === 'error'" severity="error" :closable="false" class="grow">
          Échec de l'envoi sur Vinted : {{ sent.error }}
        </Message>
        <span v-else class="hint">Article validé : il est prêt à partir sur Vinted.</span>
        <Button
          label="Repasser en relecture"
          icon="icon-undo-2"
          severity="secondary"
          :loading="working === 'unvalidate'"
          :disabled="batchRunning"
          @click="run('unvalidate', () => api.unvalidate(id))"
        />
        <Button
          :label="sent?.status === 'error' ? 'Réessayer' : 'Envoyer sur Vinted'"
          :icon="sent?.status === 'error' ? 'icon-refresh-cw' : 'icon-send'"
          :loading="working === 'send'"
          :disabled="batchRunning || !licensed"
          @click="sendToVinted"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.review {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.columns {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}

@media (max-width: 1180px) {
  .columns {
    grid-template-columns: minmax(0, 1fr);
  }
}

.col {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  min-width: 0;
}

.panel {
  padding: 1.25rem 1.375rem 1.375rem;
  gap: 1rem;
}

.tight {
  gap: 0.25rem;
}

.tight p {
  margin: 0;
}

.between {
  justify-content: space-between;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 1rem;
}

.tile {
  margin: 0;
  min-width: 0;
}

.frame {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  border: 2px solid transparent;
  background: var(--p-surface-100);
}

.tile.kept .frame {
  border-color: var(--p-apricot-400);
}

.tile img,
.placeholder {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
}

.placeholder {
  display: grid;
  place-items: center;
  padding: 0.75rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--p-red-700);
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
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: var(--p-surface-800);
  color: white;
}

figcaption {
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: 0.4rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  margin-left: -0.5rem;
}

.warn {
  color: var(--p-orange-700);
  font-weight: 600;
}

/* Collée en bas de la zone de défilement, sur toute la largeur du contenu. */
.action-bar {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin: 0 calc(-1 * var(--w-gutter)) -3rem;
  padding: 0.875rem var(--w-gutter);
  background: color-mix(in srgb, var(--p-surface-0), transparent 4%);
  border-top: 1px solid var(--p-surface-200);
  box-shadow: 0 -6px 18px rgba(46, 31, 43, 0.06);
  backdrop-filter: blur(6px);
}

.lead {
  font-size: 1.2rem;
  color: var(--p-green-700);
}

.hint {
  flex: 1;
  min-width: 14rem;
  color: var(--p-surface-700);
}

.grow {
  flex: 1;
  min-width: 14rem;
}
</style>
