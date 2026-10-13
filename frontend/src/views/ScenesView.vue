<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import ToggleSwitch from 'primevue/toggleswitch'
import { useConfirm } from 'primevue/useconfirm'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import BackgroundGallery from '@/components/BackgroundGallery.vue'
import { useNotify } from '@/composables/notify'
import { useAutoTour } from '@/composables/tour'
import { useScenes } from '@/stores/scenes'
import type { SceneDetail, SceneInfo } from '@/types'

const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const notify = useNotify()
const { scenes, load } = useScenes()

const detail = ref<SceneDetail | null>(null)
const name = ref('')
const prompt = ref('')
const saving = ref(false)
const creatingOpen = ref(false)
const newName = ref('')
useAutoTour('scenes', () => detail.value !== null && !creatingOpen.value)

const selectedSlug = computed(() => (route.params.slug as string | undefined) ?? null)
const dirty = computed(
  () => !!detail.value && (name.value !== detail.value.name || prompt.value !== detail.value.prompt),
)

async function reload() {
  try {
    await load()
  } catch (e) {
    notify.error(e)
  }
}

function show(scene: SceneDetail) {
  detail.value = scene
  name.value = scene.name
  prompt.value = scene.prompt
}

async function openScene(slug: string | null) {
  if (!slug) {
    detail.value = null
    return
  }
  try {
    show(await api.getScene(slug))
  } catch (e) {
    notify.error(e)
    detail.value = null
  }
}

onMounted(async () => {
  await reload()
  if (!selectedSlug.value && scenes.value.length) {
    router.replace({ name: 'scenes', params: { slug: scenes.value[0]!.slug } })
  }
})
watch(selectedSlug, openScene, { immediate: true })

function select(slug: string) {
  router.push({ name: 'scenes', params: { slug } })
}

async function toggle(scene: SceneInfo, enabled: boolean) {
  try {
    const updated = await api.updateScene(scene.slug, { enabled })
    if (detail.value?.slug === scene.slug) show({ ...updated, prompt: prompt.value })
    await reload()
  } catch (e) {
    notify.error(e)
  }
}

/** Échange une scène avec sa voisine, puis renumérote toutes les scènes 1, 2, 3… */
async function move(index: number, delta: -1 | 1) {
  const ordered = [...scenes.value]
  const target = index + delta
  if (target < 0 || target >= ordered.length) return
  ;[ordered[index], ordered[target]] = [ordered[target]!, ordered[index]!]
  try {
    for (const [i, scene] of ordered.entries()) {
      if (scene.order !== i + 1) await api.updateScene(scene.slug, { order: i + 1 })
    }
    await reload()
  } catch (e) {
    notify.error(e)
  }
}

async function save() {
  if (!detail.value) return
  saving.value = true
  try {
    show(await api.updateScene(detail.value.slug, { name: name.value, prompt: prompt.value }))
    await reload()
    notify.success('Scène enregistrée.')
  } catch (e) {
    notify.error(e)
  } finally {
    saving.value = false
  }
}

async function create() {
  try {
    const scene = await api.createScene(newName.value)
    creatingOpen.value = false
    newName.value = ''
    await reload()
    select(scene.slug)
  } catch (e) {
    notify.error(e)
  }
}

function removeScene() {
  const scene = detail.value
  if (!scene) return
  const n = scene.backgrounds.length
  confirm.require({
    header: `Supprimer la scène « ${scene.name} » ?`,
    message: `La scène et ses ${n} décor${n > 1 ? 's' : ''} seront définitivement supprimés.`,
    acceptProps: { label: 'Supprimer', severity: 'danger' },
    rejectProps: { label: 'Annuler', severity: 'secondary', text: true },
    accept: async () => {
      try {
        await api.deleteScene(scene.slug)
        await reload()
        router.push({ name: 'scenes' })
      } catch (e) {
        notify.error(e)
      }
    },
  })
}

async function backgroundsChanged(scene: SceneDetail) {
  if (detail.value) detail.value = { ...scene, name: detail.value.name, prompt: detail.value.prompt }
  await reload()
}
</script>

<template>
  <div class="split">
    <aside class="left">
      <h1>Scènes</h1>
      <p class="muted hint">Chaque scène active produit une photo par article.</p>
      <Button label="Nouvelle scène" icon="icon-plus" fluid @click="creatingOpen = true" />
      <div
        v-for="(scene, i) in scenes"
        :key="scene.slug"
        class="item"
        :class="{ selected: scene.slug === selectedSlug }"
        role="button"
        tabindex="0"
        @click="select(scene.slug)"
        @keydown.enter="select(scene.slug)"
      >
        <div class="text">
          <span class="title">{{ scene.name }}</span>
          <Tag v-if="scene.problem" :value="scene.problem" severity="warn" class="problem" />
        </div>
        <div class="row controls" @click.stop>
          <Button
            icon="icon-arrow-up"
            text
            rounded
            size="small"
            :disabled="i === 0"
            aria-label="Monter"
            @click="move(i, -1)"
          />
          <Button
            icon="icon-arrow-down"
            text
            rounded
            size="small"
            :disabled="i === scenes.length - 1"
            aria-label="Descendre"
            @click="move(i, 1)"
          />
          <ToggleSwitch
            :model-value="scene.enabled"
            data-tour="scene-toggle"
            :aria-label="scene.enabled ? 'Désactiver' : 'Activer'"
            @update:model-value="toggle(scene, $event)"
          />
        </div>
      </div>
    </aside>

    <section class="right">
      <template v-if="detail">
        <header class="row header">
          <h1>{{ detail.name }}</h1>
          <span class="spacer" />
          <Button
            label="Supprimer la scène"
            icon="icon-trash-2"
            severity="danger"
            text
            size="small"
            @click="removeScene"
          />
        </header>

        <div class="stack">
          <label for="scene-name">Nom</label>
          <InputText id="scene-name" v-model="name" fluid />
          <label for="scene-prompt">Consignes de mise en scène</label>
          <small class="muted">
            Envoyées à l'IA avec le décor ([Image A]) et la photo du vêtement ([Image B]).
            <code>{garment_type}</code> est remplacé par le type de vêtement.
          </small>
          <Textarea
            id="scene-prompt"
            v-model="prompt"
            style="--rows: 12"
            fluid
            class="mono"
            data-tour="scene-prompt"
          />
          <div>
            <Button
              label="Enregistrer"
              icon="icon-save"
              :disabled="!dirty"
              :loading="saving"
              @click="save"
            />
          </div>
        </div>

        <h2>Décors</h2>
        <BackgroundGallery :scene="detail" @changed="backgroundsChanged" />
      </template>
      <p v-else class="muted">Choisis une scène ou crée-en une.</p>
    </section>

    <Dialog v-model:visible="creatingOpen" header="Nouvelle scène" modal :style="{ width: '420px' }">
      <form class="stack" @submit.prevent="create">
        <label for="new-scene">Nom de la scène</label>
        <InputText id="new-scene" v-model="newName" placeholder="Ex. : Plage, Salon cosy…" autofocus />
        <div class="row">
          <Button type="submit" label="Créer" :disabled="!newName.trim()" />
          <Button
            type="button"
            label="Annuler"
            severity="secondary"
            text
            @click="creatingOpen = false"
          />
        </div>
      </form>
    </Dialog>
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
  gap: 0.5rem;
  padding: 1.75rem 1.25rem 2rem var(--w-gutter);
  overflow-y: auto;
}

.hint {
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--p-surface-200);
  border-radius: 14px;
  background: var(--p-surface-0);
  box-shadow: var(--w-shadow-card);
  cursor: pointer;
}

.item:hover {
  border-color: var(--p-surface-300);
}

.item:first-of-type {
  margin-top: 0.5rem;
}

.item.selected {
  border-color: var(--p-apricot-400);
  box-shadow: 0 0 0 2px var(--p-apricot-200);
}

.text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
}

.title {
  font-weight: 700;
}

.problem {
  font-size: 0.75rem;
}

.controls {
  gap: 0;
}

.right {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 1.75rem var(--w-gutter) 3rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.spacer {
  flex: 1;
}

label {
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
}
</style>
