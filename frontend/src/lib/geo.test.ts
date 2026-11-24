import { describe, expect, test } from 'vitest'

import { countryName, parseGeo } from './geo'

const valid = new Set(['AU', 'GB', 'MX', 'RO', 'RU'])

describe('parseGeo', () => {
  test('reads codes in any case, split by commas, spaces or semicolons', () => {
    expect(parseGeo('au, MX;ro  ru', valid)).toEqual({
      codes: ['AU', 'MX', 'RO', 'RU'],
      unknown: [],
    })
  })

  test('drops duplicates and keeps the order of input', () => {
    expect(parseGeo('mx, au, MX', valid).codes).toEqual(['MX', 'AU'])
  })

  test('reports everything that is not a country code', () => {
    expect(parseGeo('AU, UK, 12, АУ', valid)).toEqual({
      codes: ['AU'],
      unknown: ['UK', '12', 'АУ'],
    })
  })

  test('gives nothing for an empty input', () => {
    expect(parseGeo(' , ;', valid)).toEqual({ codes: [], unknown: [] })
  })
})

test('countryName shows the Russian name', () => {
  expect(countryName('AU')).toBe('Австралия')
})
