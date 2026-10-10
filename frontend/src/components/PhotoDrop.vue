<script setup lang="ts">
import Button from 'primevue/button'
import { onBeforeUnmount, ref, watch } from 'vue'

const files = defineModel<File[]>({ required: true })
defineProps<{ hint?: string }>()

const ACCEPT = '.jpg,.jpeg,.png,.webp,.avif'
const input = ref<HTMLInputElement | null>(null)
const over = ref(false)
const previews = ref<string[]>([])

// Une URL d'aperçu par fichier, libérée dès que la liste change.
watch(
  files,
  (list) => {
    previews.value.forEach(URL.revokeObjectURL)
    previews.value = list.map((f) => URL.createObjectURL(f))
  },
  { immediate: true },
)
onBeforeUnmount(() => previews.value.forEach(URL.revokeObjectURL))

function isImage(file: File) {
  return /\.(jpe?g|png|webp|avif)$/i.test(file.name)
}

function add(list: FileList | null | undefined) {
  if (!list) return
  files.value = [...files.value, ...Array.from(list).filter(isImage)]
}

function onDrop(event: DragEvent) {
  over.value = false
  add(event.dataTransfer?.files)
}

function onPick(event: Event) {
  const target = event.target as HTMLInputElement
  add(target.files)
  target.value = ''
}

function removeAt(index: number) {
  files.value = files.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div>
    <div
      class="zone"
      :class="{ over }"
      role="button"
      tabindex="0"
      @click="input?.click()"
      @keydown.enter.prevent="input?.click()"
      @dragover.prevent="over = true"
      @dragleave="over = false"
      @drop.prevent="onDrop"
    >
      <i class="pi pi-cloud-upload icon" />
      <span>Glisse tes photos ici ou <u>clique pour choisir</u></span>
      <small class="muted">{{ hint ?? 'JPG, PNG, WEBP ou AVIF' }}</small>
      <input ref="input" type="file" multiple :accept="ACCEPT" hidden @change="onPick" />
    </div>
    <div v-if="files.length" class="previews">
      <div v-for="(url, i) in previews" :key="url" class="preview">
        <img :src="url" :alt="files[i]?.name" />
        <span v-if="i === 0" class="badge">Principale</span>
        <Button
          icon="pi pi-times"
          rounded
          size="small"
          severity="secondary"
          class="remove"
          aria-label="Retirer"
          @click="removeAt(i)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 1.5rem;
  border: 2px dashed var(--p-surface-300);
  border-radius: var(--p-border-radius-lg);
  background: var(--p-surface-0);
  cursor: pointer;
  text-align: center;
}

.zone.over,
.zone:hover {
  border-color: var(--p-primary-400);
  background: var(--p-primary-50);
}

.icon {
  font-size: 1.75rem;
  color: var(--p-primary-500);
}

.previews {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.preview {
  position: relative;
  width: 96px;
  height: 128px;
}

.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
}

.badge {
  position: absolute;
  left: 4px;
  bottom: 4px;
  font-size: 0.7rem;
  padding: 0.1rem 0.35rem;
  border-radius: var(--p-border-radius-sm);
  background: var(--p-primary-600);
  color: white;
}

.remove {
  position: absolute;
  top: 4px;
  right: 4px;
}
</style>
