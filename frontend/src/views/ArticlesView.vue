<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useConfirm } from 'primevue/useconfirm'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, articleFile } from '@/api'
import ArticleForm from '@/components/ArticleForm.vue'
import ArticleList from '@/components/ArticleList.vue'
import ArticleProgress from '@/components/ArticleProgress.vue'
import ArticleReview from '@/components/ArticleReview.vue'
import QueueBanner from '@/components/QueueBanner.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import VintedBatchPanel from '@/components/VintedBatchPanel.vue'
import { useNotify } from '@/composables/notify'
import { matches, panelFor, useArticles } from '@/stores/articles'
import { useLicense } from '@/stores/license'
import { useScenes } from '@/stores/scenes'
import { useVinted } from '@/stores/vinted'
import { label, type UserInput } from '@/types'

const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const notify = useNotify()
const { articles, load, upsert, remove, stopPolling } = useArticles()
const scenes = useScenes()
const vinted = useVinted()
const { licensed } = useLicense()

const creating = ref(false)
const creatingOpen = ref(false)
const formKey = ref(0) // change pour vider le formulaire après une création
const editing = ref(false)
const savingInput = ref(false)
const working = ref(false)

const selectedId = computed(() => (route.params.id as string | undefined) ?? null)
const selected = computed(() => articles.value.find((a) => a.id === selectedId.value) ?? null)
const panel = computed(() => panelFor(selected.value))

onMounted(async () => {
  try {
    await Promise.all([load(), scenes.load(), vinted.load()])
  } catch (e) {
    notify.error(e)
  }
})
onBeforeUnmount(stopPolling)

function select(id: string) {
  router.push({ name: 'articles', params: { id } })
}

function backToList() {
  router.push({ name: 'articles' })
}

function newArticle() {
  backToList()
  creatingOpen.value = true
}

const summary = computed(() => {
  const all = articles.value
  if (!all.length) return undefined
  const review = all.filter((a) => matches('review', a)).length
  const busy = all.filter((a) => matches('busy', a)).length
  return [
    `${all.length} article${all.length > 1 ? 's' : ''}`,
    review ? `${review} à relire` : null,
    busy ? `${busy} en création` : null,
  ]
    .filter(Boolean)
    .join(' · ')
})

async function create(input: UserInput, photos: File[]) {
  creating.value = true
  try {
    upsert(await api.createArticle(input, photos))
    formKey.value += 1
    creatingOpen.value = false
    notify.success('Article ajouté : Wearo prépare les photos et l’annonce.')
  } catch (e) {
    notify.error(e)
  } finally {
    creating.value = false
  }
}

async function saveInput(input: UserInput) {
  if (!selected.value) return
  savingInput.value = true
  try {
    upsert(await api.updateInput(selected.value.id, input))
    editing.value = false
    notify.success('Saisie mise à jour. Régénère pour en tenir compte.')
  } catch (e) {
    notify.error(e)
  } finally {
    savingInput.value = false
  }
}

async function generateDraft() {
  if (!selected.value) return
  working.value = true
  try {
    upsert(await api.generate(selected.value.id))
  } catch (e) {
    notify.error(e)
  } finally {
    working.value = false
  }
}

async function sendToVinted(ids: string[]) {
  try {
    await vinted.send(ids)
  } catch (e) {
    notify.error(e)
  }
}

function deleteSelected() {
  const article = selected.value
  if (!article) return
  confirm.require({
    header: 'Supprimer cet article ?',
    message: 'Ses photos, images générées et son annonce seront définitivement supprimées.',
    acceptProps: { label: 'Supprimer', severity: 'danger' },
    rejectProps: { label: 'Annuler', severity: 'secondary', text: true },
    accept: async () => {
      try {
        await api.deleteArticle(article.id)
        remove(article.id)
        backToList()
      } catch (e) {
        notify.error(e)
      }
    },
  })
}
</script>

<template>
  <div class="page">
    <template v-if="panel === 'form'">
      <PageHeader title="Mes articles" :subtitle="summary">
        <template #actions>
          <Button label="Nouvel article" icon="icon-plus" @click="newArticle" />
        </template>
      </PageHeader>
      <QueueBanner />
      <VintedBatchPanel :articles="articles" />

      <EmptyState
        v-if="!articles.length"
        title="Ajoute ton premier vêtement"
        text="Une photo suffit : Wearo crée les photos portées et rédige l’annonce, tu n’as plus qu’à relire."
      >
        <Button label="Ajouter un vêtement" icon="icon-image-plus" @click="newArticle" />
      </EmptyState>
      <ArticleList
        v-else
        :articles="articles"
        :selected-id="selectedId"
        :sending="!!vinted.status.value?.batch.running"
        @select="select"
        @send="sendToVinted"
      />

      <Dialog
        v-model:visible="creatingOpen"
        header="Nouvel article"
        modal
        :style="{ width: '720px' }"
        :breakpoints="{ '800px': '95vw' }"
      >
        <p class="muted intro">
          Ajoute les photos et le type. Le reste est facultatif : l'IA le proposera, tu pourras
          le corriger à la relecture.
        </p>
        <ArticleForm
          :key="formKey"
          mode="create"
          :busy="creating"
          :locked="!licensed"
          @submit="create"
        />
      </Dialog>
    </template>

    <template v-else-if="selected">
      <PageHeader :title="selected.listing?.title ?? label(selected.input.garment_type)">
        <template #before>
          <RouterLink :to="{ name: 'articles' }" class="back">
            <i class="icon-chevron-left" aria-hidden="true" /> Mes articles
          </RouterLink>
        </template>
        <template #badge>
          <StatusTag :status="selected.status" :article="selected" />
        </template>
        <template v-if="panel !== 'progress'" #actions>
          <Button
            label="Modifier la saisie"
            icon="icon-pencil"
            severity="secondary"
            @click="editing = true"
          />
          <Button
            icon="icon-trash-2"
            severity="danger"
            text
            aria-label="Supprimer"
            @click="deleteSelected"
          />
        </template>
      </PageHeader>
      <QueueBanner />
      <VintedBatchPanel :articles="articles" />

      <ArticleProgress v-if="panel === 'progress'" :article="selected" />
      <ArticleReview v-else-if="panel === 'review'" :article="selected" mode="review" />
      <ArticleReview v-else-if="panel === 'validated'" :article="selected" mode="validated" />
      <ArticleReview v-else-if="panel === 'error'" :article="selected" mode="error" />
      <div v-else-if="panel === 'draft'" class="draft surface">
        <img :src="articleFile(selected, selected.photos[0] ?? '')" alt="" class="draft-photo" />
        <div class="stack">
          <h2>Génération annulée</h2>
          <p class="muted">Relance-la quand tu veux : tes photos et ta saisie sont conservées.</p>
          <div>
            <Button
              label="Générer"
              icon="icon-sparkles"
              :loading="working"
              :disabled="!licensed"
              @click="generateDraft"
            />
          </div>
        </div>
      </div>

      <Dialog
        v-model:visible="editing"
        header="Modifier la saisie"
        modal
        :style="{ width: '720px' }"
        :breakpoints="{ '800px': '95vw' }"
      >
        <ArticleForm
          mode="edit"
          :initial="selected.input"
          :busy="savingInput"
          @submit="saveInput"
          @cancel="editing = false"
        />
      </Dialog>
    </template>

    <EmptyState v-else title="Article introuvable" text="Il a peut-être été supprimé.">
      <Button label="Revenir à mes articles" severity="secondary" @click="backToList" />
    </EmptyState>
  </div>
</template>

<style scoped>
.page {
  max-width: 1240px;
  padding: 1.75rem var(--w-gutter) 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.back {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.9rem;
  text-decoration: none;
  margin-bottom: 0.25rem;
}

.intro {
  margin: 0 0 1.25rem;
}

.draft {
  display: flex;
  gap: 1.5rem;
  align-items: center;
  padding: 1.5rem;
}

.draft p {
  margin: 0;
}

.draft-photo {
  width: 150px;
  height: 200px;
  object-fit: cover;
  border-radius: 14px;
}
</style>
