import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '@/api'
import type { UpdateProgress, UpdateSnapshot } from '@/types'

import UpdateBanner from './UpdateBanner.vue'

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>()
  return {
    ...actual,
    api: { update: vi.fn(), installUpdate: vi.fn(), updateProgress: vi.fn() },
  }
})

const mocked = vi.mocked(api)

function snapshot(changes: Partial<UpdateSnapshot> = {}): UpdateSnapshot {
  return {
    current: '0.2.0',
    latest: '0.3.0',
    status: 'available',
    notes: 'Plus rapide.',
    can_install: true,
    ...changes,
  }
}

function progress(changes: Partial<UpdateProgress> = {}): UpdateProgress {
  return { state: 'downloading', received: 0, total: 1000, message: null, ...changes }
}

async function setup(snap: UpdateSnapshot) {
  mocked.update.mockResolvedValue(snap)
  const wrapper = mount(UpdateBanner, {
    global: { plugins: [PrimeVue], stubs: { teleport: true } },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

describe('UpdateBanner', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.resetAllMocks()
    document.body.innerHTML = ''
  })

  it.each(['up_to_date', 'unknown'] as const)("n'affiche rien si l'état est %s", async (status) => {
    const wrapper = await setup(snapshot({ status }))
    expect(wrapper.text()).toBe('')
  })

  it('propose la mise à jour disponible et peut être masqué', async () => {
    const wrapper = await setup(snapshot())
    expect(wrapper.text()).toContain('Nouvelle version 0.3.0 disponible')
    expect(wrapper.find('.update-banner').classes()).not.toContain('required')
    await wrapper.find('[data-test="dismiss"]').trigger('click')
    expect(wrapper.text()).toBe('')
  })

  it('reste masqué après une nouvelle vérification', async () => {
    const wrapper = await setup(snapshot())
    await wrapper.find('[data-test="dismiss"]').trigger('click')
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    expect(mocked.update).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toBe('')
  })

  it('rend la mise à jour obligatoire visible et non masquable', async () => {
    const wrapper = await setup(snapshot({ status: 'required' }))
    expect(wrapper.text()).toContain('ne fonctionne plus avec Vinted')
    expect(wrapper.find('.update-banner').classes()).toContain('required')
    expect(wrapper.find('[data-test="dismiss"]').exists()).toBe(false)
  })

  it('affiche les nouveautés', async () => {
    const wrapper = await setup(snapshot())
    await wrapper.find('[data-test="notes"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Plus rapide.')
  })

  it("n'affiche pas le lien des nouveautés sans notes", async () => {
    const wrapper = await setup(snapshot({ notes: '' }))
    expect(wrapper.find('[data-test="notes"]').exists()).toBe(false)
  })

  it("désactive l'installation hors de l'application installée", async () => {
    const wrapper = await setup(snapshot({ can_install: false }))
    expect(wrapper.find('[data-test="install"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain("uniquement depuis l'application installée")
  })

  it('télécharge avec une progression puis annonce le redémarrage', async () => {
    const wrapper = await setup(snapshot())
    mocked.installUpdate.mockResolvedValue(progress({ received: 0 }))
    mocked.updateProgress
      .mockResolvedValueOnce(progress({ received: 500 }))
      .mockResolvedValueOnce(progress({ state: 'launching', received: 1000 }))
    await wrapper.find('[data-test="install"]').trigger('click')
    await flushPromises()
    expect(mocked.installUpdate).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="install"]').exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('50')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).toContain("l'application va redémarrer")
    await vi.advanceTimersByTimeAsync(5000)
    expect(mocked.updateProgress).toHaveBeenCalledTimes(2)
  })

  it("affiche l'erreur de téléchargement et permet de réessayer", async () => {
    const wrapper = await setup(snapshot())
    mocked.installUpdate.mockResolvedValue(progress())
    mocked.updateProgress.mockResolvedValue(
      progress({ state: 'error', message: 'La mise à jour téléchargée est abîmée.' }),
    )
    await wrapper.find('[data-test="install"]').trigger('click')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).toContain('abîmée')
    expect(wrapper.find('[data-test="install"]').text()).toContain('Réessayer')
    expect(wrapper.find('[data-test="help"]').exists()).toBe(true)
  })

  it("affiche le refus de l'API (génération en cours)", async () => {
    const wrapper = await setup(snapshot())
    mocked.installUpdate.mockRejectedValue(new ApiError('Une génération est en cours.', 409))
    await wrapper.find('[data-test="install"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Une génération est en cours.')
    expect(wrapper.find('[data-test="install"]').attributes('disabled')).toBeUndefined()
  })
})
