import { useState } from 'react'

import { ApiError } from '../api/client'
import { type StreamAction, useStreamAction } from '../api/hooks'
import type { Stream } from '../api/types'
import { cx } from '../lib/cx'
import { offerColors, OTHER_COLOR } from '../lib/offers'
import { AddOffer } from './AddOffer'
import { ErrorNotice } from './ErrorNotice'
import { OfferRow } from './OfferRow'
import { SplitBar } from './SplitBar'
import styles from './StreamCard.module.css'

const TYPE_LABELS: Record<string, string> = {
  regular: 'обычный',
  default: 'замыкающий',
  forced: 'перехватывающий',
}

/** Errors after which the local copy has to be loaded from Keitaro again */
const RELOAD_CODES = ['stream_changed_in_keitaro', 'stream_not_found', 'campaign_not_found']

interface Props {
  campaignId: number
  stream: Stream
  onReload: () => void
}

export function StreamCard(props: Props) {
  return props.stream.has_offers ? (
    <OffersStream {...props} />
  ) : (
    <PlainStream stream={props.stream} />
  )
}

function StreamHead({ stream }: { stream: Stream }) {
  return (
    <header className={styles.head}>
      <span className={styles.position} title="Позиция потока">
        {stream.position}
      </span>
      <h2 id={`stream-${stream.id}`} className={styles.title}>
        {stream.name}
      </h2>
      <span className="tag">{TYPE_LABELS[stream.type] ?? stream.type}</span>
      {stream.state !== 'active' && <span className="tag">выключен</span>}
      <span className={styles.streamId}>поток #{stream.id}</span>
    </header>
  )
}

/** A stream without offers (the Google redirect): shown by name only, as in the reference video. */
function PlainStream({ stream }: { stream: Stream }) {
  return (
    <section className={cx(styles.card, styles.plain)} aria-labelledby={`stream-${stream.id}`}>
      <StreamHead stream={stream} />
      <p className={styles.note}>
        Поток без офферов. Обёртка его не меняет, настройки видны в Keitaro.
      </p>
    </section>
  )
}

function OffersStream({ campaignId, stream, onReload }: Props) {
  const action = useStreamAction(campaignId, stream.id)
  const [justPublished, setJustPublished] = useState(false)

  const colors = offerColors(stream.offers)
  const activeCount = stream.offers.filter((o) => o.state === 'active').length
  const inStream = stream.offers.filter((o) => o.state !== 'removed').map((o) => o.offer_id)
  const totalIsRight = stream.active_total === 100
  const busy = action.isPending

  function run(next: StreamAction, done?: () => void) {
    setJustPublished(false)
    action.mutate(next, {
      onSuccess: () => {
        if (next.type === 'push') setJustPublished(true)
        done?.()
      },
    })
  }

  const needsReload = action.error instanceof ApiError && RELOAD_CODES.includes(action.error.code)

  return (
    <section
      className={cx(styles.card, stream.dirty && styles.dirty)}
      aria-labelledby={`stream-${stream.id}`}
      aria-busy={busy}
    >
      <StreamHead stream={stream} />

      {stream.dirty && (
        <div className={styles.draft} role="status">
          <p className={styles.draftText}>
            <strong>Черновик.</strong> Изменения ещё не отправлены в Keitaro.
            {!totalIsRight && ` Сумма долей ${stream.active_total}%, а нужно 100%.`}
          </p>
          <div className={styles.draftActions}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy}
              onClick={() => run({ type: 'cancel' })}
            >
              Отменить
            </button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={busy || !totalIsRight}
              onClick={() => run({ type: 'push' })}
            >
              Опубликовать в Keitaro
            </button>
          </div>
        </div>
      )}
      {justPublished && !stream.dirty && (
        <p className={styles.published} role="status">
          Опубликовано в Keitaro
        </p>
      )}

      <SplitBar stream={stream} colors={colors} />

      {stream.offers.length > 0 ? (
        <ul className={styles.offers}>
          {stream.offers.map((offer) => (
            <OfferRow
              key={offer.offer_id}
              offer={offer}
              color={colors.get(offer.offer_id) ?? OTHER_COLOR}
              busy={busy}
              lastActive={offer.state === 'active' && activeCount === 1}
              onAction={(next) => run(next)}
            />
          ))}
        </ul>
      ) : (
        <p className={styles.note}>В потоке пока нет офферов.</p>
      )}

      <footer className={styles.footer}>
        <AddOffer
          exclude={inStream}
          busy={busy}
          onAdd={(offerId, done) => run({ type: 'add', offerId }, done)}
        />
        <p className={cx(styles.total, !totalIsRight && styles.totalWrong)}>
          Сумма активных долей <span className={styles.totalValue}>{stream.active_total}%</span>
        </p>
        {!totalIsRight && !stream.dirty && (
          <p className={styles.hint}>
            Так доли сейчас стоят в Keitaro. Добавьте, удалите или верните оффер, и доли
            незакреплённых офферов пересчитаются до 100%.
          </p>
        )}
      </footer>

      {action.isError && (
        <ErrorNotice
          error={action.error}
          action={
            needsReload && (
              <button type="button" className="btn btn-sm" onClick={onReload}>
                Загрузить из Keitaro
              </button>
            )
          }
        />
      )}
    </section>
  )
}
