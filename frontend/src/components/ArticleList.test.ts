import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { beforeEach, describe, expect, it } from 'vitest'

import { useListFilters } from '@/stores/articles'
import { useLicense } from '@/stores/license'
import { makeArticle } from '@/testing'
import type { LicenseSnapshot } from '@/types'

import ArticleList from './ArticleList.vue'

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

const articles = [
  makeArticle('validated', { id: 'a', created_at: '2026-10-03T10:00:00Z' }),
  makeArticle('to_review', { id: 'b', created_at: '2026-10-02T10:00:00Z' }),
  makeArticle('generating', {
    id: 'c',
    created_at: '2026-10-01T10:00:00Z',
    input: { garment_type: 'sac', brand: 'Longchamp' },
  }),
]

beforeEach(() => {
  const { filters, page } = useListFilters()
  filters.value = { query: '', status: 'all', type: null, audience: null, sort: 'recent' }
  page.value = { first: 0, rows: 24 }
})

function mountList() {
  useLicense().set({ state: 'active' } as LicenseSnapshot)
  return mount(ArticleList, {
    props: { articles, selectedId: null },
    global: { plugins: [PrimeVue] },
  })
}

function button(wrapper: ReturnType<typeof mountList>, text: string) {
  return wrapper.findAll('button').find((b) => b.text().startsWith(text))!
}

describe('ArticleList, sélection multiple', () => {
  it('n’affiche la barre d’actions qu’avec une sélection', async () => {
    const wrapper = mountList()
    expect(wrapper.find('[data-test="selection-bar"]').exists()).toBe(false)
    await wrapper.find('#check-all').setValue(true)
    expect(wrapper.find('[data-test="selection-bar"]').text()).toContain('3 sélectionnés')
  })

  it('n’envoie que les validés et ne supprime pas les articles en génération', async () => {
    const wrapper = mountList()
    await wrapper.find('#check-all').setValue(true)

    await button(wrapper, 'Envoyer sur Vinted (1)').trigger('click')
    expect(wrapper.emitted('send')).toEqual([[['a']]])

    await wrapper.find('#check-all').setValue(true)
    await button(wrapper, 'Supprimer (2)').trigger('click')
    expect(wrapper.emitted('delete')).toEqual([[['a', 'b']]])
  })
})

describe('ArticleList, recherche', () => {
  it('ne montre que les articles trouvés et propose d’effacer la recherche', async () => {
    const wrapper = mountList()
    expect(wrapper.findAll('article.card')).toHaveLength(3)

    await wrapper.find('input[aria-label="Rechercher un article"]').setValue('longchamp')
    expect(wrapper.findAll('article.card')).toHaveLength(1)

    await wrapper.find('input[aria-label="Rechercher un article"]').setValue('introuvable')
    expect(wrapper.text()).toContain('Aucun article ne correspond.')
    await button(wrapper, 'Effacer la recherche').trigger('click')
    expect(wrapper.findAll('article.card')).toHaveLength(3)
  })
})
