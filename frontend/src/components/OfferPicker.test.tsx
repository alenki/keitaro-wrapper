import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import type { OfferOption } from '../api/types'
import { OfferPicker } from './OfferPicker'

const OFFERS: OfferOption[] = [
  { id: 18001, name: '18001 Detoxin [HAIR-CL] [vsl es -] CPAHUB v2', countries: ['CL'] },
  { id: 18008, name: '18008 Detoxin [PROSTATE-IN] [article en -] OFFERIA v5', countries: ['IN'] },
]

/** The fake API answers only real searches; an empty query finds nothing. */
function mockSearch(offers: OfferOption[]) {
  const fetchMock = vi.fn(async (url: string) => {
    const query = new URL(url, 'http://test').searchParams.get('q')
    return Response.json(query ? offers : [])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPicker(props: Partial<Parameters<typeof OfferPicker>[0]> = {}) {
  const onChange = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <OfferPicker value={null} onChange={onChange} ariaLabel="Оффер" {...props} />
    </QueryClientProvider>,
  )
  return { onChange }
}

test('searches offers on the server and picks one with the keyboard', async () => {
  const fetchMock = mockSearch(OFFERS)
  const { onChange } = renderPicker()
  const user = userEvent.setup()

  await user.type(screen.getByRole('combobox', { name: 'Оффер' }), 'detox')
  await screen.findByRole('option', { name: /18008 Detoxin/ })
  await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')

  expect(onChange).toHaveBeenCalledWith(OFFERS[1])
  expect(fetchMock).toHaveBeenCalledWith('/api/offers?q=detox&limit=20', expect.anything())
})

test('picks an offer with the mouse', async () => {
  mockSearch(OFFERS)
  const { onChange } = renderPicker()
  const user = userEvent.setup()

  await user.type(screen.getByRole('combobox', { name: 'Оффер' }), '18001')
  await user.click(await screen.findByRole('option', { name: /18001 Detoxin/ }))

  expect(onChange).toHaveBeenCalledWith(OFFERS[0])
})

test('never picks a stale result that does not match what was typed', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Response.json(OFFERS)),
  )
  const { onChange } = renderPicker()
  const user = userEvent.setup()
  const input = screen.getByRole('combobox', { name: 'Оффер' })
  await user.click(input)
  await screen.findByRole('option', { name: /18001/ })

  // Enter comes before the debounced search for "18008" has answered
  await user.type(input, '18008{Enter}')

  expect(onChange).toHaveBeenCalledWith(OFFERS[1])
})

test('hides offers that are already in the stream', async () => {
  mockSearch(OFFERS)
  renderPicker({ exclude: [18001] })
  const user = userEvent.setup()

  await user.type(screen.getByRole('combobox', { name: 'Оффер' }), 'detox')

  expect(await screen.findByRole('option', { name: /18008/ })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: /18001/ })).not.toBeInTheDocument()
})

test('says so when nothing is found', async () => {
  mockSearch([])
  renderPicker()
  const user = userEvent.setup()

  await user.type(screen.getByRole('combobox', { name: 'Оффер' }), 'zzz')

  expect(await screen.findByText('Ничего не найдено')).toBeInTheDocument()
})

test('shows the chosen offer in the field', () => {
  mockSearch([])
  renderPicker({ value: OFFERS[0] })

  expect(screen.getByRole('combobox', { name: 'Оффер' })).toHaveValue(OFFERS[0].name)
})
