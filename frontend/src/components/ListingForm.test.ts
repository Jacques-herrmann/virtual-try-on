import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Listing } from '@/types'

import ListingForm from './ListingForm.vue'

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

const LISTING: Listing = { title: 'Robe Zara', description: 'Jolie robe.', color: [] }

function setup(save = vi.fn(() => Promise.resolve()), readonly = false) {
  const wrapper = mount(ListingForm, {
    props: { listing: LISTING, catalog: null, readonly, save },
    global: { plugins: [PrimeVue] },
  })
  return { wrapper, save }
}

describe('ListingForm, enregistrement automatique', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('enregistre une fois, peu après la dernière frappe', async () => {
    const { wrapper, save } = setup()
    await wrapper.find('#title').setValue('Robe Zara M')
    await vi.advanceTimersByTimeAsync(400)
    await wrapper.find('#lbrand').setValue('Zara')
    await vi.advanceTimersByTimeAsync(400)
    expect(save).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(400)
    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Robe Zara M', brand: 'Zara' }),
    )
  })

  it("n'enregistre pas une annonce sans titre", async () => {
    const { wrapper, save } = setup()
    await wrapper.find('#title').setValue('  ')
    await vi.advanceTimersByTimeAsync(2000)
    expect(save).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('le titre est vide')
  })

  it('enregistre aussitôt ce qui reste quand le formulaire disparaît', async () => {
    const { wrapper, save } = setup()
    await wrapper.find('#title').setValue('Robe Zara M')
    wrapper.unmount()
    await flushPromises()
    expect(save).toHaveBeenCalledTimes(1)
  })

  it('signale un échec', async () => {
    const { wrapper } = setup(vi.fn(() => Promise.reject(new Error('réseau'))))
    await wrapper.find('#title').setValue('Robe Zara M')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).toContain('n’a pas pu être enregistrée')
  })

  it('ne fait rien en lecture seule', async () => {
    const { wrapper, save } = setup(undefined, true)
    ;(wrapper.vm as unknown as { flush: () => Promise<void> }).flush()
    await vi.advanceTimersByTimeAsync(2000)
    expect(save).not.toHaveBeenCalled()
  })
})
