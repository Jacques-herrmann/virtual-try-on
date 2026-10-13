<script setup lang="ts">
import { computed } from 'vue'

import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useLicense } from '@/stores/license'

const CONTACT = 'contact@kaloe.fr'

const { license } = useLicense()
const site = computed(() => license.value?.site_url ?? 'https://kaloe.fr')
</script>

<template>
  <div class="page stack">
    <PageHeader title="Aide" subtitle="Comment Kaloé transforme une photo en annonce Vinted." />

    <SectionCard title="1. Ajouter un vêtement" icon="icon-image-plus">
      <ol>
        <li>Dans <strong>Articles</strong>, clique sur <strong>Nouvel article</strong>.</li>
        <li>
          Ajoute une ou plusieurs photos du vêtement (à plat, sur cintre… une photo nette et bien
          éclairée donne les meilleurs résultats) et choisis son type.
        </li>
        <li>
          Le reste (marque, taille, état, remarques) est facultatif : l’IA le propose, tu le
          corriges à la relecture.
        </li>
        <li>
          Clique sur <strong>Générer</strong>. Kaloé crée une photo par scène active et rédige
          l’annonce. Tu peux ajouter d’autres articles pendant ce temps : ils attendent leur tour.
        </li>
      </ol>
    </SectionCard>

    <SectionCard title="2. Relire et valider" icon="icon-eye">
      <p>Un article prêt passe « À relire ». Ouvre-le pour vérifier :</p>
      <ul>
        <li>
          <strong>Photos</strong> : <em>Régénérer</em> refait une photo, <em>Écarter</em> la retire
          de l’annonce. Les flèches changent l’ordre : la première photo est celle que Vinted
          affiche en premier.
        </li>
        <li>
          <strong>Annonce</strong> : titre, description, catégorie, taille, état et prix se
          modifient directement. <em>Régénérer l’annonce</em> en propose une nouvelle.
        </li>
        <li>
          Tout est bon ? Clique sur <strong>Valider l’article</strong>. Rien ne part sur Vinted
          sans ta validation ; <em>Repasser en relecture</em> annule la validation.
        </li>
      </ul>
    </SectionCard>

    <SectionCard title="3. Envoyer sur Vinted" icon="icon-send">
      <ol>
        <li>
          La première fois, va dans <strong>Réglages → Vinted</strong> et clique sur
          <strong>Connecter mon compte</strong> : connecte-toi dans la fenêtre qui s’ouvre. Kaloé
          ne connaît jamais ton mot de passe.
        </li>
        <li>
          Dans <strong>Articles</strong>, coche les articles voulus (ou <em>Tout
          sélectionner</em>), puis clique sur <strong>Envoyer sur Vinted</strong>. Seuls les
          articles validés et pas encore envoyés partent.
        </li>
        <li>
          Kaloé remplit le formulaire Vinted à ta place, article par article. Selon ton réglage,
          l’annonce est enregistrée en brouillon (à publier depuis Vinted) ou publiée directement.
          Tu peux arrêter l’envoi à tout moment.
        </li>
      </ol>
      <p class="muted">
        La même sélection sert à supprimer plusieurs articles d’un coup. La suppression est
        définitive.
      </p>
    </SectionCard>

    <SectionCard title="Scènes et décors" icon="icon-image">
      <p>
        Une scène, c’est une mise en situation (sur mannequin, sur cintre…) avec ses décors et sa
        consigne pour l’IA. Kaloé en fournit plusieurs ; dans <strong>Scènes</strong>, tu peux
        les activer ou les désactiver, ajouter tes propres décors (photos de ton intérieur, par
        exemple) ou créer une nouvelle scène. Chaque scène active produit une photo par article.
      </p>
    </SectionCard>

    <SectionCard title="Réglages utiles" icon="icon-settings">
      <ul>
        <li>
          <strong>Clé Gemini</strong> : c’est ton accès à l’IA de Google. Les générations sont
          facturées par Google sur ton compte, selon ton offre.
        </li>
        <li>
          <strong>Annonces</strong> : ajoute une signature à la fin de chaque description (tes
          remises, un mot pour tes acheteurs…) et ajuste, si tu veux, la consigne d’écriture.
        </li>
        <li>
          <strong>Abonnement</strong> : ta clé fonctionne sur 2 PC. Pour changer de PC, clique sur
          <em>Désactiver ce PC</em> sur l’ancien. <em>Gérer mon abonnement</em> ouvre tes
          factures, ta carte et la résiliation.
        </li>
      </ul>
    </SectionCard>

    <SectionCard title="Un souci ?" icon="icon-circle-help">
      <ul>
        <li>
          <strong>Une génération échoue</strong> : clique sur <em>Réessayer</em>. Si ça se répète,
          vérifie ta clé Gemini dans les Réglages (clé expirée, quota atteint).
        </li>
        <li>
          <strong>L’envoi sur Vinted s’arrête</strong> : reconnecte ton compte dans la fenêtre
          qui s’ouvre, l’envoi reprend tout seul. Un bandeau rouge en haut de l’application
          signale une mise à jour obligatoire.
        </li>
        <li>
          <strong>Installation, antivirus, données</strong> : consulte le
          <a :href="`${site}/aide`" target="_blank" rel="noopener">guide d’installation</a>.
        </li>
      </ul>
      <p>
        Toujours bloqué ? Écris à
        <a :href="`mailto:${CONTACT}`" target="_blank" rel="noopener"><i class="icon-mail" aria-hidden="true" /> {{ CONTACT }}</a>
        en joignant, si possible, les logs (<strong>Réglages → Assistance</strong>).
      </p>
    </SectionCard>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  padding: 1.75rem var(--w-gutter) 3rem;
  gap: 1.25rem;
}

ol,
ul {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  line-height: 1.55;
}

p {
  margin: 0;
  line-height: 1.55;
}

a i {
  vertical-align: -0.1em;
}
</style>
