import { type FormEvent, useId, useState } from 'react'

import type { OfferOption } from '../api/types'
import styles from './AddOffer.module.css'
import { OfferPicker } from './OfferPicker'

interface Props {
  /** Offers already in the stream */
  exclude: number[]
  busy: boolean
  onAdd: (offerId: number, done: () => void) => void
}

export function AddOffer({ exclude, busy, onAdd }: Props) {
  const inputId = useId()
  const [offer, setOffer] = useState<OfferOption | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (offer) onAdd(offer.id, () => setOffer(null))
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <label htmlFor={inputId} className="visually-hidden">
        Добавить оффер в поток
      </label>
      <OfferPicker
        inputId={inputId}
        value={offer}
        onChange={setOffer}
        exclude={exclude}
        placeholder="Добавить оффер: ID или название"
        disabled={busy}
      />
      <button type="submit" className="btn" disabled={!offer || busy}>
        Добавить
      </button>
    </form>
  )
}
