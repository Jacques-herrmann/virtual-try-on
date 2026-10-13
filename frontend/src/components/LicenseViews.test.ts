import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ConfirmDialog from 'primevue/confirmdialog'
import ToastService from 'primevue/toastservice'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { api, ApiError } from '@/api'
import { useLicense } from '@/stores/license'
import { useSettings } from '@/stores/settings'
import type { LicenseSnapshot } from '@/types'
import WelcomeView from '@/views/WelcomeView.vue'

import ArticleForm from './ArticleForm.vue'
import LicenseBanner from './LicenseBanner.vue'
import LicenseSection from './LicenseSection.vue'

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>()
  return {
    ...actual,
    api: {
      license: vi.fn(),
      activateLicense: vi.fn(),
      deactivateLicense: vi.fn(),
      licensePortal: vi.fn(),
      licenseRenew: vi.fn(),
      checkKey: vi.fn(),
    },
  }
})

// jsdom ne fournit ni ResizeObserver ni matchMedia, utilisés par les composants PrimeVue.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  addEventListener() {},
  removeEventListener() {},
})) as unknown as typeof window.matchMedia

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const mocked = vi.mocked(api)
const RENEW_URL = 'https://licence.test/renouveler?cle=KAL-ABCD-EFGH-JKMN-WXYZ'

function snapshot(changes: Partial<LicenseSnapshot> = {}): LicenseSnapshot {
  return {
    state: 'active',
    key_hint: 'KAL-…-WXYZ',
    status: 'active',
    period_end: Date.UTC(2026, 10, 12, 12) / 1000,
    devices_max: 2,
    message: null,
    site_url: 'https://licence.test',
    ...changes,
  }
}

function mountWith(component: object, props: Record<string, unknown> = {}) {
  // ConfirmDialog monté à côté : la confirmation s'affiche dans le document.
  const Host = defineComponent({
    render: () => [h(ConfirmDialog), h(component as never, props)],
  })
  return mount(Host, {
    global: { plugins: [PrimeVue, ToastService, ConfirmationService], stubs: { teleport: true } },
    attachTo: document.body,
  })
}

afterEach(() => {
  vi.resetAllMocks()
  vi.restoreAllMocks()
  useLicense().license.value = null
  useSettings().settings.value = null
  document.body.innerHTML = ''
})

describe('WelcomeView', () => {
  it("commence par la clé de licence, avec le lien d'essai", () => {
    useLicense().set(snapshot({ state: 'none', key_hint: null, status: null }))
    const wrapper = mountWith(WelcomeView)
    expect(wrapper.find('[data-test="license-step"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="gemini-step"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="trial"]').attributes('href')).toBe('https://licence.test/')
    expect(wrapper.text()).toContain('Essayer 7 jours')
  })

  it('passe à la clé Gemini une fois la licence activée', async () => {
    useLicense().set(snapshot({ state: 'none' }))
    mocked.activateLicense.mockResolvedValue(snapshot())
    const wrapper = mountWith(WelcomeView)
    await wrapper.find('#license-key').setValue('vto-abcd-efgh-jkmn-wxyz')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(mocked.activateLicense).toHaveBeenCalledWith('vto-abcd-efgh-jkmn-wxyz')
    expect(wrapper.find('[data-test="gemini-step"]').exists()).toBe(true)
    expect(push).not.toHaveBeenCalled()
  })

  it('ouvre les articles si la clé Gemini est déjà là', async () => {
    useLicense().set(snapshot({ state: 'none' }))
    useSettings().set({ has_key: true } as never)
    mocked.activateLicense.mockResolvedValue(snapshot())
    const wrapper = mountWith(WelcomeView)
    await wrapper.find('#license-key').setValue('KAL-ABCD-EFGH-JKMN-WXYZ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(push).toHaveBeenCalledWith('/articles')
  })

  it("affiche l'erreur de l'activation", async () => {
    useLicense().set(snapshot({ state: 'none' }))
    mocked.activateLicense.mockRejectedValue(
      new ApiError('Ta clé est déjà utilisée sur 2 PC (A, B).', 400),
    )
    const wrapper = mountWith(WelcomeView)
    await wrapper.find('#license-key').setValue('KAL-ABCD-EFGH-JKMN-WXYZ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[data-test="license-error"]').text()).toContain('2 PC (A, B)')
    expect(wrapper.find('[data-test="license-step"]').exists()).toBe(true)
  })
})

describe('LicenseSection', () => {
  it("montre l'état, la date et l'indice de clé", () => {
    useLicense().set(snapshot())
    const wrapper = mountWith(LicenseSection)
    expect(wrapper.find('[data-test="license-summary"]').text()).toBe('Abonnement actif.')
    expect(wrapper.find('[data-test="license-date"]').text()).toBe(
      'Renouvellement le 12 novembre 2026.',
    )
    expect(wrapper.text()).toContain('KAL-…-WXYZ')
  })

  it("annonce la fin de l'essai", () => {
    useLicense().set(snapshot({ status: 'trialing' }))
    const wrapper = mountWith(LicenseSection)
    expect(wrapper.find('[data-test="license-date"]').text()).toContain("Fin de l'essai")
  })

  it('ouvre le portail de gestion', async () => {
    useLicense().set(snapshot())
    mocked.licensePortal.mockResolvedValue({ url: 'https://billing.stripe.test/s' })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mountWith(LicenseSection)
    await wrapper.find('[data-test="portal"]').trigger('click')
    await flushPromises()
    expect(open).toHaveBeenCalledWith('https://billing.stripe.test/s', '_blank', 'noopener')
  })

  it('désactive ce PC après confirmation', async () => {
    useLicense().set(snapshot())
    mocked.deactivateLicense.mockResolvedValue(snapshot({ state: 'none', key_hint: null }))
    const wrapper = mountWith(LicenseSection)
    await wrapper.find('[data-test="deactivate"]').trigger('click')
    await flushPromises()
    expect(mocked.deactivateLicense).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Désactiver ce PC ?')
    const accept = [...document.body.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Désactiver',
    )!
    accept.click()
    await flushPromises()
    expect(mocked.deactivateLicense).toHaveBeenCalledOnce()
    expect(useLicense().license.value?.state).toBe('none')
    expect(push).toHaveBeenCalledWith('/welcome')
  })

  it('permet de changer de clé', async () => {
    useLicense().set(snapshot())
    const wrapper = mountWith(LicenseSection)
    await wrapper.find('[data-test="change"]').trigger('click')
    expect(wrapper.find('#license-key').exists()).toBe(true)
  })

  it('propose de renouveler un abonnement terminé', async () => {
    useLicense().set(snapshot({ state: 'expired', status: 'canceled' }))
    mocked.licenseRenew.mockResolvedValue({ url: RENEW_URL })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mountWith(LicenseSection)
    expect(wrapper.find('[data-test="license-summary"]').text()).toContain('terminé')
    expect(wrapper.find('[data-test="portal"]').exists()).toBe(false)
    await wrapper.find('[data-test="renew"]').trigger('click')
    await flushPromises()
    expect(open).toHaveBeenCalledWith(RENEW_URL, '_blank', 'noopener')
  })
})

describe('LicenseBanner', () => {
  it.each(['active', 'none'] as const)("n'affiche rien si la licence est %s", (state) => {
    useLicense().set(snapshot({ state }))
    expect(mountWith(LicenseBanner).find('[data-test="license-banner"]').exists()).toBe(false)
  })

  it('annonce un abonnement terminé avec un lien de renouvellement', async () => {
    useLicense().set(snapshot({ state: 'expired' }))
    mocked.licenseRenew.mockResolvedValue({ url: RENEW_URL })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const banner = mountWith(LicenseBanner).find('[data-test="license-banner"]')
    expect(banner.text()).toContain('Ton abonnement est terminé')
    expect(banner.text()).toContain('Cette action demande un abonnement actif.')
    await banner.find('[data-test="renew"]').trigger('click')
    await flushPromises()
    expect(open).toHaveBeenCalledWith(RENEW_URL, '_blank', 'noopener')
  })

  it('annonce un abonnement non vérifié', () => {
    useLicense().set(snapshot({ state: 'unverified' }))
    const banner = mountWith(LicenseBanner).find('[data-test="license-banner"]')
    expect(banner.text()).toContain('Impossible de vérifier ton abonnement')
  })

  it('montre le refus du serveur de licence', () => {
    useLicense().set(snapshot({ state: 'unverified', message: 'Ta clé est déjà utilisée.' }))
    const banner = mountWith(LicenseBanner).find('[data-test="license-banner"]')
    expect(banner.text()).toContain('Ta clé est déjà utilisée.')
  })
})

describe('ArticleForm verrouillé', () => {
  it('désactive « Générer » et explique pourquoi', () => {
    const wrapper = mountWith(ArticleForm, { mode: 'create', locked: true })
    const submit = wrapper.find('button[type="submit"]')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="locked"]').text()).toBe(
      'Cette action demande un abonnement actif.',
    )
  })
})
