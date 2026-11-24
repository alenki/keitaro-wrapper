const regionNames = new Intl.DisplayNames(['ru'], { type: 'region', fallback: 'none' })

export function countryName(code: string): string {
  try {
    return regionNames.of(code) ?? code
  } catch {
    return code
  }
}

export interface ParsedGeo {
  /** Valid codes, upper-case, without duplicates, in the order they were typed */
  codes: string[]
  /** Everything that is not a country code */
  unknown: string[]
}

/**
 * Read a geo field typed like "au, MX ro": any case, separated by commas, spaces or
 * semicolons. `validCodes` comes from the backend, which validates against ISO 3166-1.
 */
export function parseGeo(input: string, validCodes: ReadonlySet<string>): ParsedGeo {
  const codes: string[] = []
  const unknown: string[] = []
  for (const token of input.toUpperCase().split(/[\s,;]+/)) {
    if (!token) continue
    const bucket = validCodes.has(token) ? codes : unknown
    if (!bucket.includes(token)) bucket.push(token)
  }
  return { codes, unknown }
}
