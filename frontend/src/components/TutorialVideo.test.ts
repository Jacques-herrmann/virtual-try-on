import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import TutorialVideo from './TutorialVideo.vue'

// La fenêtre PrimeVue se téléporte dans <body> : on la remplace par son contenu.
const Dialog = defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) })

// jsdom ne lit ni vidéo ni piste de sous-titres : piste simulée.
const track = { mode: 'showing', activeCues: null as unknown, oncuechange: null as null | (() => void) }
Object.defineProperty(HTMLMediaElement.prototype, 'textTracks', {
  configurable: true,
  get: () => [track],
})

function mountVideo() {
  return mount(TutorialVideo, {
    props: { src: '/v.mp4', captions: '/v.vtt', title: 'Kaloé en 1 minute' },
    global: { plugins: [PrimeVue], stubs: { Dialog } },
  })
}

afterEach(() => {
  track.mode = 'showing'
  track.activeCues = null
  track.oncuechange = null
})

describe('TutorialVideo', () => {
  it('affiche le sous-titre courant par-dessus la vidéo', async () => {
    const wrapper = mountVideo()
    await wrapper.find('track').trigger('load')
    expect(track.mode).toBe('hidden')

    track.activeCues = [{ text: 'Ajoute une photo de ton vêtement.' }]
    track.oncuechange?.()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="cue"]').text()).toBe('Ajoute une photo de ton vêtement.')

    track.activeCues = []
    track.oncuechange?.()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="cue"]').exists()).toBe(false)
  })

  it('« Passer » ferme la vidéo, « C’est parti » à la fin', async () => {
    const wrapper = mountVideo()
    expect(wrapper.find('[data-test="close"]').text()).toBe('Passer')
    await wrapper.find('video').trigger('ended')
    expect(wrapper.find('[data-test="close"]').text()).toBe("C'est parti")
    await wrapper.find('[data-test="close"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('explique simplement une vidéo illisible', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wrapper = mountVideo()
    await wrapper.find('video').trigger('error')
    expect(wrapper.find('[data-test="failed"]').text()).toContain('revoir plus tard depuis l\'Aide')
    expect(wrapper.find('[data-test="close"]').text()).toBe('Fermer')
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})
