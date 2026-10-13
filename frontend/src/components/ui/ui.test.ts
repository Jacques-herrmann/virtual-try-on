import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppBanner from './AppBanner.vue'
import EmptyState from './EmptyState.vue'
import PageHeader from './PageHeader.vue'

describe('PageHeader', () => {
  it('affiche le titre, le sous-titre et les actions', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Mes articles', subtitle: '3 à relire' },
      slots: { actions: '<button>Nouvel article</button>' },
    })
    expect(wrapper.find('h1').text()).toBe('Mes articles')
    expect(wrapper.text()).toContain('3 à relire')
    expect(wrapper.find('button').text()).toBe('Nouvel article')
  })

  it('omet le sous-titre et les actions absents', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Scènes' } })
    expect(wrapper.find('.subtitle').exists()).toBe(false)
    expect(wrapper.find('.actions').exists()).toBe(false)
  })
})

describe('EmptyState', () => {
  it('affiche le message et l’action', () => {
    const wrapper = mount(EmptyState, {
      props: { title: 'Ajoute ton premier vêtement', text: 'Une photo suffit.' },
      slots: { default: '<button>Ajouter</button>' },
    })
    expect(wrapper.find('h2').text()).toBe('Ajoute ton premier vêtement')
    expect(wrapper.text()).toContain('Une photo suffit.')
    expect(wrapper.find('svg').attributes('aria-hidden')).toBe('true')
    expect(wrapper.find('button').exists()).toBe(true)
  })
})

describe('AppBanner', () => {
  it('prend le ton et l’icône par défaut du ton', () => {
    const wrapper = mount(AppBanner, { props: { tone: 'warn' }, slots: { default: 'Attention' } })
    expect(wrapper.classes()).toContain('warn')
    expect(wrapper.find('i').classes()).toContain('icon-triangle-alert')
    expect(wrapper.text()).toContain('Attention')
  })

  it('accepte une icône et des actions', () => {
    const wrapper = mount(AppBanner, {
      props: { icon: 'icon-download' },
      slots: { default: 'Mise à jour', actions: '<button>Mettre à jour</button>' },
    })
    expect(wrapper.classes()).toContain('info')
    expect(wrapper.find('i').classes()).toContain('icon-download')
    expect(wrapper.find('.actions button').exists()).toBe(true)
  })
})
