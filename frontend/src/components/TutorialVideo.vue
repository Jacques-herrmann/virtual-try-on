<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { computed, onMounted, ref } from 'vue'

/** Vidéo du tutoriel, avec ses sous-titres (WebVTT) dessinés par-dessus l'image. */
const props = defineProps<{ src: string; captions: string; poster?: string; title: string }>()
const emit = defineEmits<{ close: [] }>()

const video = ref<HTMLVideoElement | null>(null)
const cue = ref('')
const playing = ref(false)
const ended = ref(false)
const failed = ref(false)
const progress = ref(0)
const muted = ref(false)
/** La fenêtre a refusé la lecture automatique avec le son : lecture muette, bouton pour l'activer. */
const soundBlocked = ref(false)

const percent = computed(() => `${Math.round(progress.value * 1000) / 10}%`)

/** Piste chargée en mode « hidden » : le navigateur la lit, on affiche nous-mêmes le texte. */
function trackLoaded() {
  const track = video.value?.textTracks?.[0]
  if (!track) return
  track.mode = 'hidden'
  track.oncuechange = () => showCue(track.activeCues)
}

function showCue(cues: TextTrackCueList | null) {
  const active = cues?.[0] as VTTCue | undefined
  cue.value = active?.text ?? ''
}

function timeUpdate() {
  const el = video.value
  if (el?.duration) progress.value = el.currentTime / el.duration
}

function onEnded() {
  ended.value = true
  playing.value = false
  progress.value = 1
}

function onError() {
  failed.value = true
  console.warn('Vidéo du tutoriel illisible :', props.src, video.value?.error)
}

async function start() {
  const el = video.value
  if (!el) return
  try {
    el.muted = false
    await el.play()
  } catch (e) {
    if ((e as DOMException | undefined)?.name !== 'NotAllowedError') return // @error s'en charge
    el.muted = muted.value = soundBlocked.value = true
    await el.play().catch(() => {})
  }
}

onMounted(start)

function toggleSound() {
  const el = video.value
  if (!el) return
  el.muted = !el.muted
  muted.value = el.muted
  soundBlocked.value = false
}

function toggle() {
  const el = video.value
  if (!el) return
  if (el.paused) {
    if (ended.value) ended.value = false
    void el.play()
  } else el.pause()
}

function seek(event: MouseEvent) {
  const el = video.value
  const bar = event.currentTarget as HTMLElement
  if (!el?.duration) return
  const ratio = (event.clientX - bar.getBoundingClientRect().left) / bar.clientWidth
  el.currentTime = Math.min(Math.max(ratio, 0), 1) * el.duration
}
</script>

<template>
  <Dialog
    :visible="true"
    modal
    :header="title"
    :draggable="false"
    :style="{ width: 'min(1040px, 92vw)' }"
    @update:visible="(open: boolean) => !open && emit('close')"
  >
    <div class="stage">
      <video
        ref="video"
        :src="src"
        :poster="poster"
        playsinline
        preload="auto"
        @play="playing = true"
        @pause="playing = false"
        @timeupdate="timeUpdate"
        @ended="onEnded"
        @error="onError"
      >
        <track kind="subtitles" srclang="fr" label="Français" :src="captions" default @load="trackLoaded" />
      </video>
      <p v-if="cue && !failed" class="cue" data-test="cue">{{ cue }}</p>
      <Button
        v-if="soundBlocked && !failed"
        label="Activer le son"
        icon="icon-volume-2"
        class="unmute"
        data-test="unmute"
        @click="toggleSound"
      />
      <div v-if="failed" class="failed" data-test="failed">
        <i class="icon-circle-alert" aria-hidden="true" />
        <p>La vidéo n'a pas pu être lue. Tu peux la revoir plus tard depuis l'Aide.</p>
      </div>
    </div>

    <div class="controls">
      <Button
        v-if="!failed"
        :icon="playing ? 'icon-pause' : 'icon-play'"
        :aria-label="playing ? 'Pause' : 'Lecture'"
        severity="secondary"
        text
        rounded
        @click="toggle"
      />
      <div v-if="!failed" class="bar" role="progressbar" :aria-valuenow="Math.round(progress * 100)" @click="seek">
        <div class="fill" :style="{ width: percent }" />
      </div>
      <span v-else class="grow" />
      <Button
        v-if="!failed"
        :icon="muted ? 'icon-volume-x' : 'icon-volume-2'"
        :aria-label="muted ? 'Activer le son' : 'Couper le son'"
        severity="secondary"
        text
        rounded
        data-test="sound"
        @click="toggleSound"
      />
      <Button
        v-if="failed"
        label="Fermer"
        severity="secondary"
        data-test="close"
        @click="emit('close')"
      />
      <Button
        v-else-if="ended"
        label="C'est parti"
        icon="icon-arrow-right"
        iconPos="right"
        data-test="close"
        @click="emit('close')"
      />
      <Button v-else label="Passer" severity="secondary" text data-test="close" @click="emit('close')" />
    </div>
  </Dialog>
</template>

<style scoped>
.stage {
  position: relative;
  border-radius: var(--w-radius-control);
  overflow: hidden;
  background: var(--w-ink);
  aspect-ratio: 16 / 10;
}

video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.cue {
  position: absolute;
  left: 50%;
  bottom: 1.25rem;
  transform: translateX(-50%);
  max-width: 85%;
  margin: 0;
  padding: 0.55rem 1rem;
  border-radius: var(--w-radius-control);
  background: rgba(46, 31, 43, 0.82);
  color: #fff;
  font-size: 1.15rem;
  font-weight: 600;
  line-height: 1.4;
  text-align: center;
  white-space: pre-line;
}

.unmute {
  position: absolute;
  top: 1rem;
  right: 1rem;
}

.failed {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2rem;
  background: var(--w-cream);
  color: var(--w-ink);
  text-align: center;
}

.failed i {
  font-size: 2rem;
  color: var(--p-apricot-600);
}

.controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}

.bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--p-apricot-100);
  cursor: pointer;
  overflow: hidden;
}

.fill {
  height: 100%;
  background: var(--p-apricot-500);
  transition: width 0.25s linear;
}

.grow {
  flex: 1;
}
</style>
