<script setup lang="ts">
import Card from 'primevue/card'
import { useRouter } from 'vue-router'

import KeyForm from '@/components/KeyForm.vue'

const router = useRouter()
const AI_STUDIO = 'https://aistudio.google.com/apikey'
</script>

<template>
  <div class="welcome">
    <Card class="card">
      <template #title>Bienvenue dans Virtual Try-On</template>
      <template #subtitle>
        L'application utilise Gemini, l'IA de Google, pour créer tes photos et tes annonces. Il te
        faut une clé personnelle, gratuite à créer.
      </template>
      <template #content>
        <ol class="steps">
          <li>
            Ouvre <a :href="AI_STUDIO" target="_blank" rel="noopener">Google AI Studio</a> et
            connecte-toi avec ton compte Google.
          </li>
          <li>Clique sur « Créer une clé API », puis copie la clé affichée.</li>
          <li>Colle-la ci-dessous et clique sur « Vérifier ».</li>
        </ol>
        <KeyForm @saved="router.push('/articles')" />
        <p class="muted note">
          Ta clé reste sur cet ordinateur. Les générations sont facturées par Google sur ton
          compte, selon ton forfait.
        </p>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.welcome {
  min-height: 100%;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.card {
  max-width: 560px;
  width: 100%;
}

.steps {
  padding-left: 1.25rem;
  margin: 0 0 1.5rem;
  line-height: 1.7;
}

.note {
  font-size: 0.85rem;
  margin: 1.25rem 0 0;
}
</style>
