// Miroir des modèles Python (vto.core.models, vto.api.routes.*).

export const GARMENT_TYPES = [
  'haut',
  'robe',
  'jupe',
  'pantalon',
  'veste',
  'chaussures',
  'sac',
  'accessoire',
  'autre',
] as const
export type GarmentType = (typeof GARMENT_TYPES)[number]

export const AUDIENCES = ['femme', 'homme', 'enfant'] as const
export type Audience = (typeof AUDIENCES)[number]

export const CONDITIONS = [
  'Neuf',
  'Comme neuf',
  'Très bon état',
  'Bon état',
  'Satisfaisant',
] as const
export type Condition = (typeof CONDITIONS)[number]

export const PARCEL_SIZES = ['Petit', 'Moyen', 'Grand'] as const
export type ParcelSize = (typeof PARCEL_SIZES)[number]

export type ArticleStatus =
  | 'draft'
  | 'queued'
  | 'generating'
  | 'to_review'
  | 'validated'
  | 'published'
  | 'error'

export interface UserInput {
  garment_type: GarmentType
  audience?: Audience | null
  brand?: string | null
  size?: string | null
  condition?: Condition | null
  color?: string | null
  price?: number | null
  notes?: string | null
}

export interface Listing {
  title: string
  description: string
  category?: string | null
  brand?: string | null
  size?: string | null
  condition?: Condition | null
  color?: string | null
  price?: number | null
  parcel_size?: ParcelSize | null
}

export interface SceneResult {
  scene: string
  status: 'pending' | 'ok' | 'error'
  image: string | null
  error: string | null
  excluded: boolean
}

export interface GenerationJob {
  scene_slugs: string[] | null
  regenerate_listing: boolean
  queued_at: string
}

export interface Article {
  id: string
  created_at: string
  status: ArticleStatus
  input: UserInput
  photos: string[]
  scenes: SceneResult[]
  listing: Listing | null
  error: string | null
  job: GenerationJob | null
}

export interface QueueStatus {
  running: string | null
  pending: string[]
  paused: boolean
  reason: string | null
}

export interface SettingsView {
  has_key: boolean
  key_hint: string | null
  signature: string
  listing_prompt: string
  image_model: string
  text_model: string
}

export interface SceneInfo {
  slug: string
  name: string
  enabled: boolean
  order: number
  problem: string | null
}

export interface SceneDetail extends SceneInfo {
  prompt: string
  backgrounds: string[]
}
