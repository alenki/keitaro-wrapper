import { describe, expect, test } from 'vitest'

import type { StreamOffer } from '../api/types'
import { offerColors, offerStatus, OTHER_COLOR, SERIES_COLORS } from './offers'

function offer(fields: Partial<StreamOffer>): StreamOffer {
  return {
    offer_id: 18001,
    name: '18001 Detoxin',
    countries: ['CL'],
    state: 'active',
    share: 50,
    pinned: false,
    published_state: 'active',
    published_share: 50,
    ...fields,
  }
}

describe('offerStatus', () => {
  test('an offer that matches Keitaro is active', () => {
    expect(offerStatus(offer({}))).toBe('active')
  })

  test('an offer that was never pushed is new', () => {
    expect(offerStatus(offer({ published_state: null, published_share: null }))).toBe('new')
  })

  test('an offer removed in the draft will be removed', () => {
    expect(offerStatus(offer({ state: 'removed', share: 0 }))).toBe('removing')
  })

  test('an offer removed and pushed stays in the list as removed', () => {
    expect(
      offerStatus(
        offer({ state: 'removed', share: 0, published_state: 'removed', published_share: 0 }),
      ),
    ).toBe('removed')
  })

  test('a removed offer brought back in the draft is returning', () => {
    expect(offerStatus(offer({ published_state: 'removed', published_share: 0 }))).toBe('returning')
  })

  test('an offer disabled in Keitaro is disabled', () => {
    expect(offerStatus(offer({ state: 'disabled', published_state: 'disabled' }))).toBe('disabled')
  })
})

describe('offerColors', () => {
  test('gives every offer its own color in list order', () => {
    const colors = offerColors([offer({ offer_id: 1 }), offer({ offer_id: 2 })])

    expect(colors.get(1)).toBe(SERIES_COLORS[0])
    expect(colors.get(2)).toBe(SERIES_COLORS[1])
  })

  test('folds offers past the palette into one neutral color', () => {
    const offers = Array.from({ length: SERIES_COLORS.length + 1 }, (_, i) =>
      offer({ offer_id: i + 1 }),
    )

    expect(offerColors(offers).get(SERIES_COLORS.length + 1)).toBe(OTHER_COLOR)
  })
})
