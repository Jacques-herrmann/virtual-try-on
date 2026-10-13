<script setup lang="ts">
import logo from '@/assets/logo.svg'
import mark from '@/assets/logo-mark.svg'

/** Logo Wearo (fichiers générés par brand/make_logo.py). */
withDefaults(defineProps<{ height?: number; markOnly?: boolean }>(), {
  height: 28,
  markOnly: false,
})
</script>

<template>
  <img
    :src="markOnly ? mark : logo"
    :style="{ height: `${height}px` }"
    alt="Wearo"
    class="app-logo"
    draggable="false"
  />
</template>

<style scoped>
.app-logo {
  display: block;
  width: auto;
}
</style>
