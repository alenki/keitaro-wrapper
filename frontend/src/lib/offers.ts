import type { OfferOption, StreamOffer } from '../api/types'

export function offerLabel(offer: Pick<OfferOption, 'id' | 'name'>): string {
  // Emulator names start with the id already; names in a real Keitaro may not
  return offer.name.startsWith(String(offer.id)) ? offer.name : `${offer.id} ${offer.name}`
}

/**
 * Categorical palette for offers in the split bar, in a fixed order that keeps
 * neighbouring colors apart for color-blind people too (validated on a white surface).
 */
export const SERIES_COLORS = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300',
  '#6250d6',
  '#e34948',
]
export const OTHER_COLOR = '#898781'

/** Color per offer id, by its place in the stream. Removed offers keep theirs. */
export function offerColors(offers: StreamOffer[]): Map<number, string> {
  return new Map(offers.map((o, index) => [o.offer_id, SERIES_COLORS[index] ?? OTHER_COLOR]))
}

/** Dark text on the light yellow, white on everything else */
export function inkOn(color: string): string {
  return color === '#eda100' ? '#0b0b0b' : '#ffffff'
}

export type OfferStatus = 'active' | 'new' | 'returning' | 'removing' | 'removed' | 'disabled'

/** How an offer in the draft relates to what Keitaro has now. */
export function offerStatus(offer: StreamOffer): OfferStatus {
  const { state, published_state: published } = offer
  if (state === 'removed') {
    return published === 'active' || published === 'disabled' ? 'removing' : 'removed'
  }
  if (published === null) return 'new'
  if (published === 'removed') return 'returning'
  return state === 'disabled' ? 'disabled' : 'active'
}

export const STATUS_LABELS: Record<OfferStatus, string | null> = {
  active: null,
  new: 'новый',
  returning: 'вернётся',
  removing: 'будет удалён',
  removed: 'удалён',
  disabled: 'выключен в Keitaro',
}
