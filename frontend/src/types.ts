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

/** « robe » → « Robe » : libellé affiché d'un type de vêtement ou d'un public. */
export function label(value: string): string {
  return value ? value[0]!.toUpperCase() + value.slice(1) : value
}

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
  /** Identifiant de catégorie Vinted, ex. « 1779 ». */
  category?: string | null
  brand?: string | null
  size?: string | null
  condition?: Condition | null
  /** 0 à 2 couleurs Vinted. */
  color: string[]
  price?: number | null
  parcel_size?: ParcelSize | null
}

export interface VintedResult {
  mode: 'draft' | 'publish'
  status: 'ok' | 'partial' | 'error'
  missing_fields: string[]
  url: string | null
  error: string | null
  sent_at: string
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
  /** Ordre choisi des photos pour Vinted (null = ordre par défaut). */
  gallery: string[] | null
  /** Photos qui partiront réellement sur Vinted, dans l'ordre. */
  effective_gallery: string[]
  vinted: VintedResult | null
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
  vinted_mode: VintedMode
  tutorial: TutorialState
}

/** Ce que le vendeur a déjà vu : la vidéo d'accueil et les visites guidées (par écran). */
export interface TutorialState {
  video_seen: boolean
  tours_seen: string[]
}

export type VintedMode = 'draft' | 'publish'

export interface VintedBatch {
  running: boolean
  paused_reason: 'login_required' | null
  current: string | null
  done: number
  total: number
  failed: number
  message: string | null
}

export interface VintedStatus {
  connected: boolean | null
  connecting: boolean
  data_revision: string | null
  data_source: 'remote' | 'cache' | 'bundled' | null
  batch: VintedBatch
}

export interface CategoryNode {
  id: number
  label: string
  children: CategoryNode[]
  size_group?: string
}

export interface VintedCatalog {
  revision: string
  catalog: CategoryNode[]
  size_groups: Record<string, string[]>
  colors: string[]
  conditions: Condition[]
  parcel_sizes: ParcelSize[]
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

export type UpdateStatus = 'unknown' | 'up_to_date' | 'available' | 'required'

export interface UpdateSnapshot {
  current: string
  latest: string | null
  status: UpdateStatus
  notes: string
  can_install: boolean
}

export interface UpdateProgress {
  state: 'idle' | 'downloading' | 'launching' | 'error'
  received: number
  total: number | null
  message: string | null
}

export type LicenseState = 'none' | 'active' | 'expired' | 'unverified'

export interface LicenseSnapshot {
  state: LicenseState
  key_hint: string | null
  status: string | null
  /** Fin de la période payée (secondes depuis 1970), ou null. */
  period_end: number | null
  devices_max: number
  /** Dernier refus du serveur de licence à montrer (2 PC déjà actifs…). */
  message: string | null
  /** Site de vente : essai, renouvellement, aide. */
  site_url: string
}
