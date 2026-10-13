import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import type { SettingsView } from '@/types'

// driver.js simulé : on garde la configuration reçue et on pilote la fin de visite à la main.
interface FakeDriver {
  config: any
  drive: ReturnType<typeof vi.fn>
  destroy: ReturnType<typeof vi.fn>
  /** Le vendeur ferme la visite (Terminer, Échap) : driver.js appelle onDestroyStarted. */
  close: () => void
}
const drivers: FakeDriver[] = []
vi.mock('driver.js', () => ({
  driver: (config: any) => {
    const instance: FakeDriver = {
      config,
      drive: vi.fn(),
      destroy: vi.fn(),
      close: () => config.onDestroyStarted?.(undefined, {}, {}),
    }
    drivers.push(instance)
    return instance
  },
}))
vi.mock('driver.js/dist/driver.css', () => ({}))
vi.mock('@/tour.css', () => ({}))
vi.mock('@/tours', () => ({
  TOURS: {
    articles: [
      { target: '[data-tour="a"]', title: 'A', text: 'a' },
      { target: '[data-tour="b"]', title: 'B', text: 'b' },
    ],
    scenes: [{ target: '[data-tour="s"]', title: 'S', text: 's' }],
  },
}))

const updateSettings = vi.fn()
vi.mock('@/api', () => ({ api: { updateSettings: (c: unknown) => updateSettings(c) } }))

const { useSettings } = await import('@/stores/settings')
const { useTutorial } = await import('@/stores/tutorial')
const { useAutoTour, useTour } = await import('./tour')

function settingsWith(tours_seen: string[] = []): SettingsView {
  return {
    has_key: true,
    key_hint: '1234',
    signature: '',
    listing_prompt: '',
    image_model: 'i',
    text_model: 't',
    vinted_mode: 'draft',
    tutorial: { video_seen: true, tours_seen },
  }
}

function addTargets(...names: string[]) {
  for (const name of names) {
    const el = document.createElement('div')
    el.dataset.tour = name
    document.body.appendChild(el)
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  drivers.length = 0
  updateSettings.mockReset().mockResolvedValue({})
  useSettings().set(settingsWith())
  useTutorial().videoOpen.value = false
})

afterEach(() => {
  useTour().stop('articles')
  useTour().stop('scenes')
  document.body.innerHTML = ''
  vi.useRealTimers()
})

async function settle() {
  await vi.runAllTimersAsync()
}

describe('useTour', () => {
  it('lance la visite avec les étapes présentes et la marque vue à la fin', async () => {
    addTargets('a', 'b')
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    expect(drivers).toHaveLength(1)
    expect(drivers[0]!.config.steps.map((s: any) => s.popover.title)).toEqual(['A', 'B'])
    expect(drivers[0]!.drive).toHaveBeenCalled()

    drivers[0]!.close()
    await settle()
    expect(updateSettings).toHaveBeenCalledWith({
      tutorial: { video_seen: true, tours_seen: ['articles'] },
    })
  })

  it('saute les étapes dont l’élément est absent', async () => {
    addTargets('b')
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    expect(drivers[0]!.config.steps.map((s: any) => s.popover.title)).toEqual(['B'])
  })

  it('ne lance rien et ne marque rien sans aucun élément', async () => {
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    expect(drivers).toHaveLength(0)
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('ne relance pas une visite déjà vue', async () => {
    useSettings().set(settingsWith(['articles']))
    addTargets('a')
    await useTour().maybeStart('articles')
    expect(drivers).toHaveLength(0)
  })

  it('attend la fermeture de la vidéo', async () => {
    useTutorial().videoOpen.value = true
    addTargets('a')
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    expect(drivers).toHaveLength(0)
  })

  it('une visite interrompue (écran quitté) n’est pas marquée vue', async () => {
    addTargets('a')
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    useTour().stop('articles')
    await settle()
    expect(updateSettings).not.toHaveBeenCalled()
  })

  it('joue les visites une à une', async () => {
    addTargets('a', 's')
    const first = useTour().maybeStart('articles')
    const second = useTour().maybeStart('scenes')
    await settle()
    await Promise.all([first, second])
    expect(drivers).toHaveLength(1)

    drivers[0]!.close()
    await settle()
    expect(drivers).toHaveLength(2)
    expect(drivers[1]!.config.steps[0].popover.title).toBe('S')
  })

  it('reste silencieuse si l’enregistrement échoue', async () => {
    updateSettings.mockRejectedValue(new Error('hors ligne'))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    addTargets('a')
    const run = useTour().maybeStart('articles')
    await settle()
    await run
    drivers[0]!.close()
    await settle()
    expect(useSettings().settings.value?.tutorial.tours_seen).toEqual(['articles'])
    warn.mockRestore()
  })

  it('« Relancer les visites » vide la liste des visites vues', async () => {
    useSettings().set(settingsWith(['articles', 'scenes']))
    await useTour().resetTours()
    expect(updateSettings).toHaveBeenCalledWith({
      tutorial: { video_seen: true, tours_seen: [] },
    })
  })
})

describe('useAutoTour', () => {
  it('lance la visite quand la condition devient vraie et la ferme sans la marquer sinon', async () => {
    addTargets('a')
    const ready = ref(false)
    const Screen = defineComponent({
      setup() {
        useAutoTour('articles', () => ready.value)
        return () => h('div')
      },
    })
    const wrapper = mount(Screen)
    await settle()
    expect(drivers).toHaveLength(0)

    ready.value = true
    await settle()
    expect(drivers).toHaveLength(1)

    ready.value = false
    await settle()
    expect(updateSettings).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('ferme la visite quand l’écran disparaît', async () => {
    addTargets('a')
    const Screen = defineComponent({
      setup() {
        useAutoTour('articles')
        return () => h('div')
      },
    })
    const wrapper = mount(Screen)
    await settle()
    expect(drivers).toHaveLength(1)
    wrapper.unmount()
    await settle()
    expect(updateSettings).not.toHaveBeenCalled()
    // L'écran revient : la visite aussi.
    const again = mount(Screen)
    await settle()
    expect(drivers).toHaveLength(2)
    again.unmount()
  })
})

describe('closeIntro', () => {
  it('ferme la vidéo et la marque vue, ce qui libère les visites', async () => {
    const settings = settingsWith()
    settings.tutorial.video_seen = false
    useSettings().set(settings)
    const { videoOpen, closeIntro } = useTutorial()
    videoOpen.value = true
    await closeIntro()
    expect(videoOpen.value).toBe(false)
    expect(updateSettings).toHaveBeenCalledWith({ tutorial: { video_seen: true, tours_seen: [] } })
  })
})
