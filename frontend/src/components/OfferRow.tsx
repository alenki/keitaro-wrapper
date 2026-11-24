import type { StreamAction } from '../api/hooks'
import type { StreamOffer } from '../api/types'
import { cx } from '../lib/cx'
import { countryName } from '../lib/geo'
import { offerLabel, offerStatus, STATUS_LABELS } from '../lib/offers'
import { PinIcon } from './Icons'
import styles from './OfferRow.module.css'

interface Props {
  offer: StreamOffer
  color: string
  busy: boolean
  /** The last active offer can't be removed */
  lastActive: boolean
  onAction: (action: StreamAction) => void
}

export function OfferRow({ offer, color, busy, lastActive, onAction }: Props) {
  const status = offerStatus(offer)
  const statusLabel = STATUS_LABELS[status]
  const removed = offer.state === 'removed'
  const offerId = offer.offer_id
  // "было N%" when the draft changed a share that Keitaro already has
  const previous =
    !removed &&
    (offer.published_state === 'active' || offer.published_state === 'disabled') &&
    offer.published_share !== offer.share
      ? offer.published_share
      : null

  return (
    <li className={cx(styles.row, removed && styles.rowRemoved)}>
      <span
        className={styles.swatch}
        style={{ background: removed ? 'transparent' : color, borderColor: color }}
        aria-hidden="true"
      />
      <div className={styles.info}>
        <span className={styles.name}>{offerLabel({ id: offerId, name: offer.name })}</span>
        <span className={styles.tags}>
          {offer.countries.map((code) => (
            <span key={code} className="tag" title={countryName(code)}>
              {code}
            </span>
          ))}
          {statusLabel && (
            <span className={cx('tag', styles.status, styles[status])}>{statusLabel}</span>
          )}
        </span>
      </div>

      <div className={styles.share}>
        <span className={styles.shareValue}>{offer.share}%</span>
        {previous !== null && <span className={styles.previous}>было {previous}%</span>}
      </div>

      {removed ? (
        <span className={styles.pinPlaceholder} />
      ) : (
        <button
          type="button"
          className={cx('btn btn-quiet btn-sm', styles.pin, offer.pinned && styles.pinned)}
          aria-pressed={offer.pinned}
          aria-label={offer.pinned ? 'Открепить долю' : 'Закрепить долю'}
          title={
            offer.pinned
              ? 'Доля закреплена и не меняется при пересчёте'
              : 'Закрепить долю: при пересчёте она не изменится'
          }
          disabled={busy || offer.state !== 'active'}
          onClick={() => onAction({ type: 'pin', offerId, pinned: !offer.pinned })}
        >
          <PinIcon filled={offer.pinned} />
        </button>
      )}

      {removed ? (
        <button
          type="button"
          className={cx('btn btn-sm', styles.action)}
          disabled={busy}
          onClick={() => onAction({ type: 'restore', offerId })}
        >
          Вернуть
        </button>
      ) : (
        <button
          type="button"
          className={cx('btn btn-sm', styles.action)}
          disabled={busy || lastActive}
          title={lastActive ? 'Последний активный оффер удалить нельзя' : undefined}
          onClick={() => onAction({ type: 'remove', offerId })}
        >
          Удалить
        </button>
      )}
    </li>
  )
}
