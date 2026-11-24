import type { Stream } from '../api/types'
import { cx } from '../lib/cx'
import { inkOn, OTHER_COLOR } from '../lib/offers'
import { PinIcon } from './Icons'
import styles from './SplitBar.module.css'

interface Segment {
  offerId: number
  name: string
  share: number
  pinned: boolean
}

interface Props {
  stream: Stream
  colors: Map<number, string>
}

/** How the traffic of a stream is split between offers; with a draft also what Keitaro has now. */
export function SplitBar({ stream, colors }: Props) {
  const draft: Segment[] = stream.offers
    .filter((o) => o.state === 'active' && o.share > 0)
    .map((o) => ({ offerId: o.offer_id, name: o.name, share: o.share, pinned: o.pinned }))
  const published: Segment[] = stream.offers
    .filter((o) => o.published_state === 'active' && (o.published_share ?? 0) > 0)
    .map((o) => ({
      offerId: o.offer_id,
      name: o.name,
      share: o.published_share ?? 0,
      pinned: false,
    }))

  return (
    <div className={styles.bars}>
      {stream.dirty && (
        <Bar label="Сейчас в Keitaro" segments={published} colors={colors} compact />
      )}
      <Bar
        label={stream.dirty ? 'После публикации' : 'Распределение трафика'}
        segments={draft}
        colors={colors}
      />
    </div>
  )
}

function Bar({
  label,
  segments,
  colors,
  compact = false,
}: {
  label: string
  segments: Segment[]
  colors: Map<number, string>
  compact?: boolean
}) {
  const total = segments.reduce((sum, segment) => sum + segment.share, 0)
  const description = segments.length
    ? segments.map((s) => `оффер ${s.offerId}: ${s.share}%`).join(', ')
    : 'активных офферов нет'

  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}</span>
      <div
        className={cx(styles.bar, compact && styles.compact)}
        role="img"
        aria-label={`${label}: ${description}`}
      >
        {segments.map((segment) => {
          const color = colors.get(segment.offerId) ?? OTHER_COLOR
          return (
            <div
              key={segment.offerId}
              className={styles.segment}
              style={{ flexGrow: segment.share, background: color, color: inkOn(color) }}
              title={`${segment.name}: ${segment.share}%${segment.pinned ? ', закреплена' : ''}`}
            >
              {!compact && segment.share >= 9 && (
                <span className={styles.value}>
                  {segment.pinned && <PinIcon size={11} filled />}
                  {segment.share}%
                </span>
              )}
            </div>
          )
        })}
        {total < 100 && (
          <div
            className={styles.unassigned}
            style={{ flexGrow: 100 - total }}
            title={`Не распределено: ${100 - total}%`}
          />
        )}
      </div>
    </div>
  )
}
