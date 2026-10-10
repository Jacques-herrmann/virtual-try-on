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
import { useNotify } from '@/composables/notify'
import { panelFor, useArticles } from '@/stores/articles'
import { useScenes } from '@/stores/scenes'
import { label, type UserInput } from '@/types'

const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const notify = useNotify()
const { articles, load, upsert, remove, stopPolling } = useArticles()
const scenes = useScenes()

const creating = ref(false)
const formKey = ref(0) // change pour vider le formulaire après une création
const editing = ref(false)
const savingInput = ref(false)
const working = ref(false)

const selectedId = computed(() => (route.params.id as string | undefined) ?? null)
const selected = computed(() => articles.value.find((a) => a.id === selectedId.value) ?? null)
const panel = computed(() => panelFor(selected.value))

onMounted(async () => {
  try {
    await Promise.all([load(), scenes.load()])
  } catch (e) {
    notify.error(e)
  }
})
onBeforeUnmount(stopPolling)

function select(id: string) {
  router.push({ name: 'articles', params: { id } })
}

function newArticle() {
  router.push({ name: 'articles' })
}

async function create(input: UserInput, photos: File[]) {
  creating.value = true
  try {
    upsert(await api.createArticle(input, photos))
    formKey.value += 1
    notify.success('Article ajouté à la file de génération.')
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
        newArticle()
      } catch (e) {
        notify.error(e)
      }
    },
  })
}
</script>

<template>
  <div class="split">
    <aside class="left">
      <QueueBanner />
      <ArticleList
        :articles="articles"
        :selected-id="selectedId"
        @select="select"
        @create="newArticle"
      />
    </aside>

    <section class="right">
      <template v-if="panel === 'form'">
        <h1>Nouvel article</h1>
        <p class="muted">
          Ajoute les photos et le type. Les autres informations sont facultatives : l'IA les
          proposera, tu pourras les corriger à la relecture.
        </p>
        <ArticleForm :key="formKey" mode="create" :busy="creating" @submit="create" />
      </template>

      <template v-else-if="selected">
        <header class="row header">
          <h1 class="title">{{ selected.listing?.title ?? label(selected.input.garment_type) }}</h1>
          <StatusTag :status="selected.status" />
          <span class="spacer" />
          <Button
            v-if="panel !== 'progress'"
            label="Modifier la saisie"
            icon="pi pi-pencil"
            severity="secondary"
            size="small"
            text
            @click="editing = true"
          />
          <Button
            v-if="panel !== 'progress'"
            icon="pi pi-trash"
            severity="danger"
            size="small"
            text
            aria-label="Supprimer"
            @click="deleteSelected"
          />
        </header>

        <ArticleProgress v-if="panel === 'progress'" :article="selected" />
        <ArticleReview v-else-if="panel === 'review'" :article="selected" mode="review" />
        <ArticleReview v-else-if="panel === 'validated'" :article="selected" mode="validated" />
        <ArticleReview v-else-if="panel === 'error'" :article="selected" mode="error" />
        <div v-else-if="panel === 'draft'" class="stack">
          <p class="muted">Génération annulée. Relance-la quand tu veux.</p>
          <img :src="articleFile(selected, selected.photos[0] ?? '')" alt="" class="draft-photo" />
          <div>
            <Button label="Générer" icon="pi pi-sparkles" :loading="working" @click="generateDraft" />
          </div>
        </div>

        <Dialog
          v-model:visible="editing"
          header="Modifier la saisie"
          modal
          :style="{ width: '640px' }"
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

      <p v-else class="muted">Article introuvable.</p>
    </section>
  </div>
</template>

<style scoped>
.split {
  display: flex;
  height: 100%;
}

.left {
  width: 330px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  overflow-y: auto;
  border-right: 1px solid var(--p-content-border-color);
}

.right {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 1.5rem 2rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 980px;
}

.header {
  gap: 0.75rem;
}

.title {
  font-size: 1.35rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spacer {
  flex: 1;
}

.draft-photo {
  width: 180px;
  height: 240px;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
}
</style>
