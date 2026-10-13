<script setup lang="ts">
import Button from 'primevue/button'
import Select from 'primevue/select'
import { useConfirm } from 'primevue/useconfirm'
import { computed, ref } from 'vue'

import { api, sceneFile } from '@/api'
import PhotoDrop from '@/components/PhotoDrop.vue'
import { useNotify } from '@/composables/notify'
import { AUDIENCES, GARMENT_TYPES, label, type SceneDetail } from '@/types'

const props = defineProps<{ scene: SceneDetail }>()
const emit = defineEmits<{ changed: [scene: SceneDetail] }>()

const confirm = useConfirm()
const notify = useNotify()

const ROOT = ''
const subfolderOptions = [
  { value: ROOT, label: 'Tous types (utilisé par défaut)' },
  ...GARMENT_TYPES.map((t) => ({ value: t, label: `Type : ${label(t)}` })),
  ...AUDIENCES.map((a) => ({ value: a, label: `Public : ${label(a)}` })),
]

const files = ref<File[]>([])
const subfolder = ref(ROOT)
const uploading = ref(false)

/** Décors regroupés par sous-dossier, « Tous types » (racine) en premier. */
const groups = computed(() => {
  const byFolder = new Map<string, string[]>()
  for (const path of props.scene.backgrounds) {
    const folder = path.includes('/') ? path.split('/')[0]! : ROOT
    byFolder.set(folder, [...(byFolder.get(folder) ?? []), path])
  }
  return [...byFolder.entries()]
    .sort(([a], [b]) => (a === ROOT ? -1 : b === ROOT ? 1 : a.localeCompare(b)))
    .map(([folder, paths]) => ({
      folder,
      title: folder === ROOT ? 'Tous types' : label(folder),
      paths,
    }))
})

async function upload() {
  uploading.value = true
  try {
    emit('changed', await api.addBackgrounds(props.scene.slug, files.value, subfolder.value || null))
    files.value = []
    notify.success('Décors ajoutés.')
  } catch (e) {
    notify.error(e)
  } finally {
    uploading.value = false
  }
}

function remove(path: string) {
  confirm.require({
    header: 'Supprimer ce décor ?',
    message: 'L’image sera définitivement supprimée de la scène.',
    acceptProps: { label: 'Supprimer', severity: 'danger' },
    rejectProps: { label: 'Annuler', severity: 'secondary', text: true },
    accept: async () => {
      try {
        await api.deleteBackground(props.scene.slug, path)
        emit('changed', await api.getScene(props.scene.slug))
      } catch (e) {
        notify.error(e)
      }
    },
  })
}
</script>

<template>
  <div class="stack">
    <p class="muted">
      Pour chaque article, un décor est tiré au hasard : d'abord dans le dossier du type de
      vêtement, puis dans celui du public, sinon dans « Tous types ».
    </p>

    <p v-if="!scene.backgrounds.length" class="warn">
      Aucun décor : cette scène ne sera pas utilisée tant que tu n'en ajoutes pas.
    </p>

    <div v-for="group in groups" :key="group.folder" class="group">
      <h4>{{ group.title }} <span class="muted">({{ group.paths.length }})</span></h4>
      <div class="grid">
        <div v-for="path in group.paths" :key="path" class="bg">
          <img :src="sceneFile(scene.slug, path)" :alt="path" loading="lazy" />
          <Button
            icon="icon-trash-2"
            rounded
            size="small"
            severity="danger"
            class="remove"
            aria-label="Supprimer le décor"
            @click="remove(path)"
          />
        </div>
      </div>
    </div>

    <div class="add stack" data-tour="backgrounds">
      <h4>Ajouter des décors</h4>
      <PhotoDrop v-model="files" hint="Photos de décor vides (sans vêtement), JPG ou PNG" />
      <div v-if="files.length" class="row">
        <Select
          v-model="subfolder"
          :options="subfolderOptions"
          option-label="label"
          option-value="value"
          class="subfolder"
        />
        <Button
          :label="`Ajouter ${files.length} décor${files.length > 1 ? 's' : ''}`"
          icon="icon-upload"
          :loading="uploading"
          @click="upload"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
h4 {
  margin: 0 0 0.5rem;
  font-weight: 600;
}

.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.bg {
  position: relative;
  width: 120px;
  height: 160px;
}

.bg img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
  background: var(--p-surface-100);
}

.remove {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
}

.bg:hover .remove,
.remove:focus-visible {
  opacity: 1;
}

.add {
  padding-top: 1rem;
  border-top: 1px solid var(--p-content-border-color);
}

.subfolder {
  min-width: 260px;
}

.warn {
  color: var(--p-orange-600);
}
</style>
