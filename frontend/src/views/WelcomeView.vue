<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import KeyForm from '@/components/KeyForm.vue'
import LicenseForm from '@/components/LicenseForm.vue'
import TutorialVideo from '@/components/TutorialVideo.vue'
import AppLogo from '@/components/ui/AppLogo.vue'
import { useLicense } from '@/stores/license'
import { useSettings } from '@/stores/settings'
import { KEY_VIDEO, videoAvailable } from '@/stores/tutorial'

const router = useRouter()
const { license } = useLicense()
const { settings } = useSettings()
const AI_STUDIO = 'https://aistudio.google.com/apikey'

// Étape 1 : clé de licence ; étape 2 : clé Gemini.
const step = computed(() => ((license.value?.state ?? 'none') === 'none' ? 'license' : 'gemini'))

// Lien vers la vidéo de la clé Gemini, seulement si elle est livrée avec l'app.
const keyVideoReady = ref(false)
const keyVideoOpen = ref(false)
onMounted(async () => {
  keyVideoReady.value = await videoAvailable(KEY_VIDEO.src)
})

function licenseSaved() {
  if (settings.value?.has_key) router.push('/articles')
}
</script>

<template>
  <div class="welcome">
    <div class="column">
      <AppLogo :height="40" class="logo" />

      <ol class="stepper" aria-label="Étapes">
        <li :class="{ current: step === 'license', done: step === 'gemini' }">
          <span class="dot"><i v-if="step === 'gemini'" class="icon-check" /><template v-else>1</template></span>
          Licence
        </li>
        <li class="line" aria-hidden="true" />
        <li :class="{ current: step === 'gemini' }">
          <span class="dot">2</span>
          Clé Gemini
        </li>
      </ol>

      <section v-if="step === 'license'" class="card surface" data-test="license-step">
        <h1>Bienvenue dans Kaloé</h1>
        <p class="lead muted">
          Pour commencer, colle la clé de licence reçue par e-mail après ton inscription.
        </p>
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
      </section>

      <section v-else class="card surface" data-test="gemini-step">
        <h1>Ta clé Gemini</h1>
        <p class="lead muted">
          Kaloé utilise Gemini, l'IA de Google, pour créer tes photos et tes annonces. Il te faut
          une clé personnelle, gratuite à créer.
        </p>
        <ol class="howto">
          <li>
            <span class="num">1</span>
            <span>
              Ouvre <a :href="AI_STUDIO" target="_blank" rel="noopener">Google AI Studio</a> et
              connecte-toi avec ton compte Google.
            </span>
          </li>
          <li>
            <span class="num">2</span>
            <span>Clique sur « Créer une clé API », puis copie la clé affichée.</span>
          </li>
          <li>
            <span class="num">3</span>
            <span>Colle-la ci-dessous et clique sur « Vérifier ».</span>
          </li>
        </ol>
        <button
          v-if="keyVideoReady"
          type="button"
          class="watch"
          data-test="key-video"
          @click="keyVideoOpen = true"
        >
          <i class="icon-circle-play" aria-hidden="true" /> Voir comment faire (30 s)
        </button>
        <KeyForm @saved="router.push('/articles')" />
        <p class="muted note">
          <i class="icon-key-round" aria-hidden="true" />
          Ta clé reste sur cet ordinateur. Les générations sont facturées par Google sur ton
          compte, selon ton forfait.
        </p>
      </section>
    </div>
    <TutorialVideo v-if="keyVideoOpen" v-bind="KEY_VIDEO" @close="keyVideoOpen = false" />
  </div>
</template>

<style scoped>
.watch {
  all: unset;
  cursor: pointer;
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 700;
  color: var(--p-apricot-700);
}

.watch:hover {
  color: var(--p-apricot-800);
  text-decoration: underline;
}

.watch:focus-visible {
  outline: 2px solid var(--p-apricot-600);
  outline-offset: 2px;
}

.welcome {
  min-height: 100%;
  display: grid;
  place-items: center;
  padding: 2.5rem 1.5rem;
  background:
    radial-gradient(circle at 15% 10%, var(--p-apricot-50), transparent 45%),
    var(--w-cream);
}

.column {
  width: 100%;
  max-width: 540px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.75rem;
}

.stepper {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--p-text-muted-color);
}

.stepper li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.stepper .line {
  width: 3rem;
  height: 2px;
  background: var(--p-surface-300);
}

.dot {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--p-surface-200);
  color: var(--p-surface-700);
  font-size: 0.85rem;
  font-weight: 700;
}

.stepper .current {
  color: var(--p-text-color);
}

.current .dot {
  background: var(--p-apricot-500);
  color: var(--w-ink);
}

.done .dot {
  background: var(--p-green-100);
  color: var(--p-green-700);
}

.card {
  width: 100%;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.lead {
  margin: 0 0 0.5rem;
}

.howto {
  list-style: none;
  margin: 0 0 0.5rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.howto li {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.num {
  flex-shrink: 0;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--p-apricot-100);
  color: var(--p-apricot-800);
  font-size: 0.8rem;
  font-weight: 800;
}

.note {
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
}
</style>
