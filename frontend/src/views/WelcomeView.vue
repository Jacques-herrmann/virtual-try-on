<script setup lang="ts">
import Card from 'primevue/card'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import KeyForm from '@/components/KeyForm.vue'
import LicenseForm from '@/components/LicenseForm.vue'
import { useLicense } from '@/stores/license'
import { useSettings } from '@/stores/settings'

const router = useRouter()
const { license } = useLicense()
const { settings } = useSettings()
const AI_STUDIO = 'https://aistudio.google.com/apikey'

// Étape 1 : clé de licence ; étape 2 : clé Gemini.
const step = computed(() => ((license.value?.state ?? 'none') === 'none' ? 'license' : 'gemini'))

function licenseSaved() {
  if (settings.value?.has_key) router.push('/articles')
}
</script>

<template>
  <div class="welcome">
    <Card v-if="step === 'license'" class="card" data-test="license-step">
      <template #title>Bienvenue dans Wearo</template>
      <template #subtitle>
        Pour commencer, colle la clé de licence reçue par e-mail après ton inscription.
      </template>
      <template #content>
        <LicenseForm @saved="licenseSaved" />
        <p class="muted note">
          Pas encore de clé ?
          <a
            data-test="trial"
            :href="`${license?.site_url ?? ''}/`"
            target="_blank"
            rel="noopener"
          >Essayer 7 jours</a>
          ·
          <a :href="`${license?.site_url ?? ''}/retrouver`" target="_blank" rel="noopener">
            Retrouver ma clé
          </a>
        </p>
      </template>
    </Card>

    <Card v-else class="card" data-test="gemini-step">
      <template #title>Ta clé Gemini</template>
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
