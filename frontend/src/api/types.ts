// Shapes of the backend API (see backend/app/api/schemas.py)

export type OfferState = 'active' | 'disabled' | 'removed'

export interface Named {
  id: number
  name: string
}

export interface CampaignForm {
  prefix: string
  countries: string[]
  domains: Named[]
  groups: Named[]
  traffic_sources: Named[]
}

export interface OfferOption {
  id: number
  name: string
  countries: string[]
}

export interface CampaignListItem {
  id: number
  name: string
  alias: string
  state: string
  updated_at: string | null
}

export interface StreamOffer {
  offer_id: number
  name: string
  countries: string[]
  state: OfferState
  share: number
  pinned: boolean
  published_state: OfferState | null
  published_share: number | null
}

export interface Stream {
  id: number
  name: string
  position: number
  type: string
  state: string
  has_offers: boolean
  dirty: boolean
  active_total: number
  offers: StreamOffer[]
}

export interface Campaign {
  id: number
  name: string
  alias: string
  state: string
  domain: Named | null
  group: Named | null
  traffic_source: Named | null
  keitaro_url: string
  synced_at: string
  streams: Stream[]
}

export interface NewCampaign {
  name: string
  geo: string[]
  offer_id: number
  domain_id: number
  group_id: number
  traffic_source_id: number
}

export interface FieldError {
  field: string
  message: string
}
