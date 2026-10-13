<script setup lang="ts">
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import { computed, ref, watch } from 'vue'

import { articleFile } from '@/api'
import { MAX_GALLERY, candidates, include, isCustom, move, remove } from '@/gallery'
import type { Article } from '@/types'

const props = defineProps<{ article: Article; version?: string; saving?: boolean }>()
const emit = defineEmits<{ save: [gallery: string[] | null] }>()

const order = ref<string[]>([...props.article.effective_gallery])
const dragged = ref<number | null>(null)

// L'article change (régénération, écartement d'une image) : on repart de son état.
watch(
  () => props.article.effective_gallery,
  (gallery) => {
    order.value = [...gallery]
  },
)

const dirty = computed(
  () => JSON.stringify(order.value) !== JSON.stringify(props.article.effective_gallery),
)
const others = computed(() => candidates(props.article).filter((p) => !order.value.includes(p)))
const full = computed(() => order.value.length >= MAX_GALLERY)

function isOriginal(path: string) {
  return props.article.photos.includes(path)
}

function src(path: string) {
  return articleFile(props.article, path, isOriginal(path) ? undefined : props.version)
}

function drop(index: number) {
  if (dragged.value !== null) order.value = move(order.value, dragged.value, index)
  dragged.value = null
}

function save() {
  emit('save', isCustom(props.article, order.value) ? order.value : null)
}

defineExpose({ dirty })
</script>

<template>
  <div class="stack">
    <p class="muted small">
      Fais glisser les photos pour choisir leur ordre sur Vinted : la première sera la photo
      principale de l’annonce.
    </p>
    <ol class="strip">
      <li
        v-for="(path, index) in order"
        :key="path"
        class="thumb"
        :class="{ dragging: dragged === index }"
        draggable="true"
        @dragstart="dragged = index"
        @dragend="dragged = null"
        @dragover.prevent
        @drop.prevent="drop(index)"
      >
        <img :src="src(path)" alt="" draggable="false" />
        <span class="rank">{{ index + 1 }}</span>
        <span v-if="isOriginal(path)" class="tag">Photo d’origine</span>
        <div class="tools">
          <Button
            icon="icon-arrow-left"
            size="small"
            text
            rounded
            aria-label="Avancer"
            :disabled="index === 0"
            @click="order = move(order, index, index - 1)"
          />
          <Button
            icon="icon-x"
            size="small"
            text
            rounded
            severity="secondary"
            aria-label="Retirer de l’annonce"
            :disabled="order.length === 1"
            @click="order = remove(order, path)"
          />
          <Button
            icon="icon-arrow-right"
            size="small"
            text
            rounded
            aria-label="Reculer"
            :disabled="index === order.length - 1"
            @click="order = move(order, index, index + 1)"
          />
        </div>
      </li>
    </ol>

    <div v-if="others.length" class="stack">
      <span class="small">Autres photos de l’article</span>
      <div class="strip">
        <label v-for="path in others" :key="path" class="thumb other">
          <img :src="src(path)" alt="" />
          <span class="include">
            <Checkbox
              :model-value="false"
              binary
              :disabled="full"
              @update:model-value="order = include(order, path)"
            />
            Inclure
          </span>
        </label>
      </div>
    </div>

    <div class="row">
      <span class="muted small">{{ order.length }} / {{ MAX_GALLERY }} photos</span>
      <span class="spacer" />
      <Button
        v-if="article.gallery"
        label="Ordre par défaut"
        severity="secondary"
        size="small"
        text
        :disabled="saving"
        @click="emit('save', null)"
      />
      <Button
        v-if="dirty"
        label="Annuler"
        severity="secondary"
        size="small"
        text
        @click="order = [...article.effective_gallery]"
      />
      <Button
        label="Enregistrer l’ordre"
        icon="icon-save"
        size="small"
        :disabled="!dirty"
        :loading="saving"
        @click="save"
      />
    </div>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.thumb {
  position: relative;
  width: 108px;
  cursor: grab;
}

.thumb.dragging {
  opacity: 0.4;
}

.thumb img {
  display: block;
  width: 108px;
  height: 144px;
  object-fit: cover;
  border-radius: var(--p-border-radius-md);
  background: var(--p-surface-100);
}

.rank {
  position: absolute;
  top: 6px;
  left: 6px;
  min-width: 1.4rem;
  padding: 0 0.3rem;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 999px;
  background: var(--p-primary-600);
  color: white;
}

.tag {
  position: absolute;
  bottom: 38px;
  left: 6px;
  font-size: 0.7rem;
  padding: 0.1rem 0.35rem;
  border-radius: var(--p-border-radius-sm);
  background: var(--p-surface-700);
  color: white;
}

.tools {
  display: flex;
  justify-content: space-between;
}

.other {
  cursor: default;
}

.other img {
  opacity: 0.6;
}

.include {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.3rem;
  font-size: 0.8rem;
}

.small {
  font-size: 0.85rem;
}

.spacer {
  flex: 1;
}
</style>
