import { useState } from 'react'
import { Link } from 'react-router'

import { useCampaigns } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { cx } from '../lib/cx'
import { formatKeitaroTime } from '../lib/format'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import styles from './CampaignsPage.module.css'

export function CampaignsPage() {
  useDocumentTitle('Кампании')
  const campaigns = useCampaigns()
  const [query, setQuery] = useState('')

  const search = query.trim().toLowerCase()
  const rows = (campaigns.data ?? []).filter(
    (c) => !search || c.name.toLowerCase().includes(search) || String(c.id) === search,
  )

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <h1>Кампании</h1>
          <p className={styles.lead}>
            Кампании из Keitaro, доступные по API-ключу. Откройте кампанию, чтобы менять офферы в её
            потоках.
          </p>
        </div>
        <Link to="/campaigns/new" className="btn btn-primary">
          Новая кампания
        </Link>
      </div>

      <div className={styles.toolbar}>
        <input
          type="search"
          className="input"
          placeholder="Поиск по названию или ID"
          aria-label="Поиск кампаний"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {campaigns.data && (
          <span className={styles.count}>
            {rows.length} из {campaigns.data.length}
          </span>
        )}
      </div>

      {campaigns.isPending && <p className="muted">Загружаем кампании из Keitaro...</p>}
      {campaigns.isError && (
        <ErrorNotice
          error={campaigns.error}
          action={
            <button type="button" className="btn btn-sm" onClick={() => campaigns.refetch()}>
              Повторить
            </button>
          }
        />
      )}

      {campaigns.data && rows.length > 0 && (
        <ul className={styles.list}>
          {rows.map((campaign) => (
            <li key={campaign.id}>
              <Link to={`/campaigns/${campaign.id}`} className={styles.row}>
                <span
                  className={cx(styles.state, campaign.state === 'active' && styles.stateOn)}
                  title={campaign.state === 'active' ? 'Включена' : 'Выключена'}
                />
                <span className={styles.id}>#{campaign.id}</span>
                <span className={styles.name}>{campaign.name}</span>
                <span className={styles.alias}>{campaign.alias}</span>
                <span className={styles.updated}>{formatKeitaroTime(campaign.updated_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {campaigns.data && rows.length === 0 && (
        <div className={styles.empty}>
          {campaigns.data.length === 0 ? (
            <>
              <p>В Keitaro пока нет кампаний.</p>
              <Link to="/campaigns/new" className="btn btn-primary">
                Создать первую
              </Link>
            </>
          ) : (
            <p>Ничего не нашлось по запросу.</p>
          )}
        </div>
      )}
    </div>
  )
}
