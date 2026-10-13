<script setup lang="ts">
import Button from 'primevue/button'
import { useConfirm } from 'primevue/useconfirm'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api'
import LicenseForm from '@/components/LicenseForm.vue'
import { useNotify } from '@/composables/notify'
import { formatDate, useLicense } from '@/stores/license'

const { license, set } = useLicense()
const notify = useNotify()
const confirm = useConfirm()
const router = useRouter()

const changing = ref(false)
const working = ref<'portal' | 'renew' | 'deactivate' | null>(null)

const summary = computed(() => {
  const l = license.value
  if (!l) return ''
  if (l.state === 'expired') return 'Ton abonnement est terminé.'
  if (l.state === 'unverified') {
    return l.message ?? 'Impossible de vérifier ton abonnement. Vérifie ta connexion Internet.'
  }
  if (l.state === 'none') return 'Aucune licence sur ce PC.'
  if (l.status === 'trialing') return 'Essai gratuit en cours.'
  if (l.status === 'past_due') {
    return 'Le dernier paiement a échoué : mets à jour ta carte pour garder ton abonnement.'
  }
  return 'Abonnement actif.'
})

const dateLine = computed(() => {
  const l = license.value
  const date = formatDate(l?.period_end ?? null)
  if (!l || l.state !== 'active' || !date) return null
  return l.status === 'trialing' ? `Fin de l'essai le ${date}.` : `Renouvellement le ${date}.`
})

async function openPage(kind: 'portal' | 'renew') {
  working.value = kind
  try {
    const { url } = await (kind === 'portal' ? api.licensePortal() : api.licenseRenew())
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    notify.error(e)
  } finally {
    working.value = null
  }
}

function deactivate() {
  confirm.require({
    header: 'Désactiver ce PC ?',
    message:
      'La génération et l’envoi sur Vinted ne seront plus possibles sur ce PC. Ta clé pourra être utilisée sur un autre PC.',
    acceptProps: { label: 'Désactiver', severity: 'danger' },
    rejectProps: { label: 'Annuler', severity: 'secondary', text: true },
    accept: async () => {
      working.value = 'deactivate'
      try {
        set(await api.deactivateLicense())
        notify.success('Ce PC est désactivé.')
        router.push('/welcome')
      } catch (e) {
        notify.error(e)
      } finally {
        working.value = null
      }
    },
  })
}

function saved() {
  changing.value = false
  notify.success('Licence activée.')
}
</script>

<template>
  <div v-if="license" class="stack" data-test="license-section">
    <div class="stack tight">
      <span data-test="license-summary">{{ summary }}</span>
      <span v-if="dateLine" class="muted" data-test="license-date">{{ dateLine }}</span>
      <span v-if="license.key_hint" class="muted">
        Clé : <code>{{ license.key_hint }}</code> · utilisable sur {{ license.devices_max }} PC
      </span>
    </div>

    <LicenseForm v-if="changing" cancellable @saved="saved" @cancel="changing = false" />
    <div v-else class="row wrap">
      <Button
        v-if="license.state === 'active'"
        data-test="portal"
        label="Gérer mon abonnement"
        icon="icon-credit-card"
        :loading="working === 'portal'"
        @click="openPage('portal')"
      />
      <Button
        v-if="license.state === 'expired'"
        data-test="renew"
        label="Renouveler"
        icon="icon-refresh-cw"
        :loading="working === 'renew'"
        @click="openPage('renew')"
      />
      <Button
        data-test="change"
        label="Changer de clé"
        severity="secondary"
        @click="changing = true"
      />
      <Button
        v-if="license.state !== 'none'"
        data-test="deactivate"
        label="Désactiver ce PC"
        icon="icon-power"
        severity="secondary"
        text
        :loading="working === 'deactivate'"
        @click="deactivate"
      />
    </div>
  </div>
</template>

<style scoped>
.tight {
  gap: 0.25rem;
}

.wrap {
  flex-wrap: wrap;
}
</style>
