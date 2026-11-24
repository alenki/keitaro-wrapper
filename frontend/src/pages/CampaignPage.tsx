import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'

import { useCampaign, useFetchCampaign } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { ArrowLeftIcon, ExternalIcon, RefreshIcon } from '../components/Icons'
import { StreamCard } from '../components/StreamCard'
import { formatTime } from '../lib/format'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import styles from './CampaignPage.module.css'
import { NotFoundPage } from './NotFoundPage'

export function CampaignPage() {
  const { id } = useParams()
  const campaignId = Number(id)
  if (!Number.isInteger(campaignId) || campaignId <= 0) return <NotFoundPage />
  return <CampaignEditor key={campaignId} campaignId={campaignId} />
}

function CampaignEditor({ campaignId }: { campaignId: number }) {
  const campaign = useCampaign(campaignId)
  const reload = useFetchCampaign(campaignId)
  const location = useLocation()
  const navigate = useNavigate()
  // Shown once after the creator redirects here
  const [justCreated] = useState(Boolean((location.state as { created?: boolean } | null)?.created))
  useDocumentTitle(campaign.data?.name ?? `Кампания #${campaignId}`)

  useEffect(() => {
    if (location.state) navigate(location.pathname, { replace: true, state: null })
  }, [location.pathname, location.state, navigate])

  if (campaign.isPending) {
    return <p className="muted">Загружаем кампанию...</p>
  }
  if (campaign.isError) {
    return (
      <div className={styles.page}>
        <BackLink />
        <ErrorNotice error={campaign.error} />
      </div>
    )
  }

  const data = campaign.data
  const hasDraft = data.streams.some((stream) => stream.dirty)

  function reloadFromKeitaro() {
    const confirmed =
      !hasDraft ||
      window.confirm('Неопубликованные изменения пропадут. Загрузить кампанию из Keitaro заново?')
    if (confirmed) reload.mutate()
  }

  return (
    <div className={styles.page}>
      <BackLink />
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <span className={styles.kicker}>Кампания #{data.id}</span>
          <h1 className={styles.title}>{data.name}</h1>
          <dl className={styles.meta}>
            <div>
              <dt>Идентификатор</dt>
              <dd className="mono">{data.alias}</dd>
            </div>
            <div>
              <dt>Домен</dt>
              <dd>{data.domain?.name ?? 'не задан'}</dd>
            </div>
            <div>
              <dt>Группа</dt>
              <dd>{data.group?.name ?? 'не задана'}</dd>
            </div>
            <div>
              <dt>Источник</dt>
              <dd>{data.traffic_source?.name ?? 'не задан'}</dd>
            </div>
            <div>
              <dt>Загружено из Keitaro</dt>
              <dd>{formatTime(data.synced_at)}</dd>
            </div>
          </dl>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className="btn"
            onClick={reloadFromKeitaro}
            disabled={reload.isPending}
          >
            <RefreshIcon />
            {reload.isPending ? 'Загружаем...' : 'Загрузить из Keitaro'}
          </button>
          <a className="btn" href={data.keitaro_url} target="_blank" rel="noreferrer">
            Открыть в Keitaro
            <ExternalIcon />
          </a>
        </div>
      </header>

      {justCreated && (
        <div className="alert alert-success" role="status">
          Кампания создана в Keitaro: домен, группа, источник и два потока настроены.
        </div>
      )}
      {reload.isError && <ErrorNotice error={reload.error} />}

      <div className={styles.streams}>
        {data.streams.map((stream) => (
          <StreamCard
            // A fresh load from Keitaro starts every card clean, without old errors
            key={`${stream.id}:${data.synced_at}`}
            campaignId={data.id}
            stream={stream}
            onReload={reloadFromKeitaro}
          />
        ))}
        {data.streams.length === 0 && <p className="muted">В кампании нет потоков.</p>}
      </div>
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/" className={styles.back}>
      <ArrowLeftIcon />
      Все кампании
    </Link>
  )
}
