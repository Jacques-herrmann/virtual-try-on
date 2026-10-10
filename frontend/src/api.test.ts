import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, articleFile, disconnected } from './api'
import type { Article } from './types'

function respond(status: number, body?: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  disconnected.value = false
})

describe('api', () => {
  it('renvoie le JSON en cas de succès', async () => {
    respond(200, { running: null, pending: [], paused: false, reason: null })
    expect(await api.queue()).toEqual({ running: null, pending: [], paused: false, reason: null })
  })

  it('transforme une erreur en ApiError avec le message du serveur', async () => {
    respond(400, { message: 'Ta clé Gemini est invalide.' })
    const error = await api.checkKey('x').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.message).toBe('Ta clé Gemini est invalide.')
    expect(error.status).toBe(400)
  })

  it('utilise un message générique si le corps est illisible', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('oops', { status: 500 })))
    const error = await api.queue().catch((e) => e)
    expect(error.message).toBe('Une erreur inattendue est survenue.')
  })

  it('signale la déconnexion quand le serveur ne répond pas', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await api.queue().catch((e) => e)
    expect(error.status).toBe(0)
    expect(disconnected.value).toBe(true)
    respond(200, { running: null, pending: [], paused: false, reason: null })
    await api.queue()
    expect(disconnected.value).toBe(false)
  })

  it('envoie le JSON avec le bon en-tête', async () => {
    const fetchMock = respond(200, {})
    await api.generate('a1', { scenes: ['cintre'] })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/articles/a1/generate')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ scenes: ['cintre'] })
  })

  it("envoie les photos en multipart sans les champs vides", async () => {
    const fetchMock = respond(201, {})
    const photo = new File(['x'], 'robe.jpg', { type: 'image/jpeg' })
    await api.createArticle({ garment_type: 'robe', brand: '', size: 'M', price: null }, [photo])
    const body: FormData = fetchMock.mock.calls[0][1].body
    expect(body.get('garment_type')).toBe('robe')
    expect(body.get('size')).toBe('M')
    expect(body.has('brand')).toBe(false)
    expect(body.has('price')).toBe(false)
    expect((body.get('photos') as File).name).toBe('robe.jpg')
  })

  it('gère les réponses 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(api.deleteArticle('a1')).resolves.toBeUndefined()
  })
})

describe('articleFile', () => {
  it('encode le chemin et ajoute la version', () => {
    const article = { id: 'a 1' } as Article
    expect(articleFile(article, 'generated/cintre.jpg', '2026-10-10T12:00')).toBe(
      '/files/articles/a%201/generated/cintre.jpg?v=2026-10-10T12%3A00',
    )
  })
})
