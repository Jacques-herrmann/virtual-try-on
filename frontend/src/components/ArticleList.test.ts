import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { describe, expect, it } from 'vitest'

import { useLicense } from '@/stores/license'
import { makeArticle } from '@/testing'
import type { LicenseSnapshot } from '@/types'

import ArticleList from './ArticleList.vue'

const articles = [
  makeArticle('validated', { id: 'a' }),
  makeArticle('to_review', { id: 'b' }),
  makeArticle('generating', { id: 'c' }),
]

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
