import { type KeyboardEvent, useId, useState } from 'react'

import { useOfferSearch } from '../api/hooks'
import type { OfferOption } from '../api/types'
import { offerLabel } from '../lib/offers'
import { useDebouncedValue } from '../lib/useDebouncedValue'
import styles from './OfferPicker.module.css'

interface Props {
  value: OfferOption | null
  onChange: (offer: OfferOption | null) => void
  /** Offers that can't be picked, for example the ones already in the stream */
  exclude?: number[]
  inputId?: string
  ariaLabel?: string
  placeholder?: string
  invalid?: boolean
  disabled?: boolean
}

/** Same rule as the backend search, so results of the previous query never show unfiltered */
function matches(offer: OfferOption, text: string): boolean {
  const query = text.trim().toLowerCase()
  return !query || String(offer.id).startsWith(query) || offer.name.toLowerCase().includes(query)
}

/** Offer search with autocomplete: the list comes from /api/offers as you type. */
export function OfferPicker({
  value,
  onChange,
  exclude = [],
  inputId,
  ariaLabel,
  placeholder = 'ID или название оффера',
  invalid,
  disabled,
}: Props) {
  const listId = useId()
  // null while the user is not typing: the field then shows the chosen offer
  const [draft, setDraft] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const query = useDebouncedValue((draft ?? '').trim(), 250)
  const search = useOfferSearch(query, open)
  const options = (search.data ?? []).filter(
    (offer) => !exclude.includes(offer.id) && matches(offer, draft ?? ''),
  )
  const activeIndex = Math.min(active, options.length - 1)
  const activeOption = open ? options[activeIndex] : undefined

  function choose(offer: OfferOption) {
    onChange(offer)
    setDraft(null)
    setOpen(false)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (open) setActive(Math.min(activeIndex + 1, options.length - 1))
      else setOpen(true)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive(Math.max(activeIndex - 1, 0))
    } else if (event.key === 'Enter' && activeOption) {
      event.preventDefault()
      choose(activeOption)
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    }
  }

  return (
    <div className={styles.picker}>
      <input
        id={inputId}
        className="input"
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeOption ? `${listId}-${activeOption.id}` : undefined}
        aria-invalid={invalid || undefined}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        disabled={disabled}
        value={draft ?? (value ? offerLabel(value) : '')}
        onChange={(event) => {
          setDraft(event.target.value)
          setActive(0)
          setOpen(true)
          if (value) onChange(null)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && (
        <div className={styles.popup}>
          {options.length > 0 ? (
            <ul id={listId} role="listbox" className={styles.list}>
              {options.map((offer, index) => (
                <li
                  key={offer.id}
                  id={`${listId}-${offer.id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? styles.active : undefined}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActive(index)}
                  onClick={() => choose(offer)}
                >
                  <span className={styles.name}>{offerLabel(offer)}</span>
                  {offer.countries.length > 0 && (
                    <span className={styles.countries}>{offer.countries.join(' ')}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className={styles.empty} role="status">
              {search.isFetching
                ? 'Ищем...'
                : search.isError
                  ? 'Не удалось загрузить офферы'
                  : 'Ничего не найдено'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
