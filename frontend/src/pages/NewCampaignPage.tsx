import { type FormEvent, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useCampaignForm, useCreateCampaign } from '../api/hooks'
import type { CampaignForm, Named, OfferOption } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { OfferPicker } from '../components/OfferPicker'
import { cx } from '../lib/cx'
import { countryName, parseGeo } from '../lib/geo'
import { offerLabel } from '../lib/offers'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import styles from './NewCampaignPage.module.css'

type Field = 'name' | 'geo' | 'offer_id' | 'domain_id' | 'group_id' | 'traffic_source_id'

const FIELD_IDS: Record<Field, string> = {
  name: 'campaign-name',
  geo: 'campaign-geo',
  offer_id: 'campaign-offer',
  domain_id: 'campaign-domain',
  group_id: 'campaign-group',
  traffic_source_id: 'campaign-source',
}

export function NewCampaignPage() {
  useDocumentTitle('Новая кампания')
  const form = useCampaignForm()

  return (
    <div className={styles.page}>
      <div>
        <h1>Новая кампания</h1>
        <p className={styles.lead}>
          Кампания с двумя потоками: посетители из выбранных стран уходят на Google, все остальные
          на оффер.
        </p>
      </div>
      {form.isPending && <p className="muted">Загружаем настройки из Keitaro...</p>}
      {form.isError && (
        <ErrorNotice
          error={form.error}
          action={
            <button type="button" className="btn btn-sm" onClick={() => form.refetch()}>
              Повторить
            </button>
          }
        />
      )}
      {form.data && <CampaignCreator options={form.data} />}
    </div>
  )
}

/** A list with one item needs no choice */
function onlyId(items: Named[]): string {
  return items.length === 1 ? String(items[0].id) : ''
}

/** Field errors from a 422 (details) or a duplicate name (409) */
function serverErrors(error: unknown): Partial<Record<Field, string>> {
  if (!(error instanceof ApiError)) return {}
  if (error.code === 'duplicate_name') return { name: error.message }
  const errors: Partial<Record<Field, string>> = {}
  for (const detail of error.details) {
    const field = detail.field.split('.')[0] as Field
    if (field in FIELD_IDS) errors[field] ??= detail.message
  }
  return errors
}

function CampaignCreator({ options }: { options: CampaignForm }) {
  const navigate = useNavigate()
  const create = useCreateCampaign()
  const validCodes = useMemo(() => new Set(options.countries), [options.countries])

  const [name, setName] = useState('')
  const [geoText, setGeoText] = useState('')
  const [offer, setOffer] = useState<OfferOption | null>(null)
  const [domainId, setDomainId] = useState(onlyId(options.domains))
  const [groupId, setGroupId] = useState(onlyId(options.groups))
  const [sourceId, setSourceId] = useState(onlyId(options.traffic_sources))
  const [submitted, setSubmitted] = useState(false)

  const geo = parseGeo(geoText, validCodes)
  const trimmed = name.trim()
  const fullName = trimmed.startsWith(options.prefix) ? trimmed : options.prefix + trimmed

  const missing: Partial<Record<Field, string>> = {}
  if (!trimmed) missing.name = 'Введите название'
  if (geo.unknown.length) missing.geo = `Таких кодов стран нет: ${geo.unknown.join(', ')}`
  else if (!geo.codes.length) missing.geo = 'Укажите хотя бы одну страну'
  if (!offer) missing.offer_id = 'Выберите оффер'
  if (!domainId) missing.domain_id = 'Выберите домен'
  if (!groupId) missing.group_id = 'Выберите группу'
  if (!sourceId) missing.traffic_source_id = 'Выберите источник'

  const errors = { ...(submitted ? missing : {}), ...serverErrors(create.error) }
  const formError =
    create.error && Object.keys(serverErrors(create.error)).length === 0 ? create.error : null

  // A server error belongs to the values it was about; editing clears it
  function edit<T>(setter: (value: T) => void) {
    return (value: T) => {
      if (create.isError) create.reset()
      setter(value)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    const firstMissing = (Object.keys(FIELD_IDS) as Field[]).find((field) => missing[field])
    if (firstMissing || !offer) {
      if (firstMissing) document.getElementById(FIELD_IDS[firstMissing])?.focus()
      return
    }
    create.mutate(
      {
        name: trimmed,
        geo: geo.codes,
        offer_id: offer.id,
        domain_id: Number(domainId),
        group_id: Number(groupId),
        traffic_source_id: Number(sourceId),
      },
      {
        onSuccess: (campaign) =>
          navigate(`/campaigns/${campaign.id}`, { state: { created: true } }),
      },
    )
  }

  const nameOf = (items: Named[], id: string) =>
    items.find((item) => String(item.id) === id)?.name ?? 'не выбран'

  return (
    <div className={styles.layout}>
      <form className={styles.card} onSubmit={submit} noValidate>
        <div className={styles.field}>
          <label htmlFor={FIELD_IDS.name}>Название</label>
          <div className={cx(styles.prefixed, errors.name && styles.prefixedInvalid)}>
            <span className={styles.prefix}>{options.prefix}</span>
            <input
              id={FIELD_IDS.name}
              className={styles.prefixedInput}
              value={name}
              onChange={(event) => edit(setName)(event.target.value)}
              placeholder="campaign1"
              maxLength={200}
              autoComplete="off"
              aria-invalid={Boolean(errors.name) || undefined}
              aria-describedby="campaign-name-hint"
            />
          </div>
          <FieldMessage id="campaign-name-hint" error={errors.name}>
            Префикс из задания подставляется сам.
          </FieldMessage>
        </div>

        <div className={styles.field}>
          <label htmlFor={FIELD_IDS.geo}>Гео</label>
          <input
            id={FIELD_IDS.geo}
            className="input"
            value={geoText}
            onChange={(event) => edit(setGeoText)(event.target.value)}
            placeholder="MX, AU, RO"
            autoComplete="off"
            spellCheck={false}
            aria-invalid={Boolean(errors.geo) || undefined}
            aria-describedby="campaign-geo-hint"
          />
          {(geo.codes.length > 0 || geo.unknown.length > 0) && (
            <div className={styles.chips}>
              {geo.codes.map((code) => (
                <span key={code} className={styles.chip}>
                  <b>{code}</b> {countryName(code)}
                </span>
              ))}
              {geo.unknown.map((code) => (
                <span key={code} className={cx(styles.chip, styles.chipBad)}>
                  <b>{code}</b> не страна
                </span>
              ))}
            </div>
          )}
          <FieldMessage id="campaign-geo-hint" error={errors.geo}>
            Коды стран ISO через запятую. Посетители из этих стран уйдут на Google.
          </FieldMessage>
        </div>

        <div className={styles.field}>
          <label htmlFor={FIELD_IDS.offer_id}>Оффер</label>
          <OfferPicker
            inputId={FIELD_IDS.offer_id}
            value={offer}
            onChange={edit(setOffer)}
            placeholder="Поиск по ID или названию"
            invalid={Boolean(errors.offer_id)}
          />
          <FieldMessage error={errors.offer_id}>
            Все остальные посетители уйдут на него.
          </FieldMessage>
        </div>

        <fieldset className={styles.tracker}>
          <legend>Настройки трекера</legend>
          <SelectField
            id={FIELD_IDS.domain_id}
            label="Домен"
            items={options.domains}
            value={domainId}
            onChange={edit(setDomainId)}
            error={errors.domain_id}
          />
          <SelectField
            id={FIELD_IDS.group_id}
            label="Группа"
            items={options.groups}
            value={groupId}
            onChange={edit(setGroupId)}
            error={errors.group_id}
          />
          <SelectField
            id={FIELD_IDS.traffic_source_id}
            label="Источник"
            items={options.traffic_sources}
            value={sourceId}
            onChange={edit(setSourceId)}
            error={errors.traffic_source_id}
          />
        </fieldset>

        {formError && <ErrorNotice error={formError} />}

        <button
          type="submit"
          className={cx('btn btn-primary', styles.submit)}
          disabled={create.isPending}
        >
          {create.isPending ? 'Создаём в Keitaro...' : 'Создать кампанию'}
        </button>
      </form>

      <aside className={styles.preview} aria-label="Что будет создано">
        <h2 className={styles.previewTitle}>Что будет в Keitaro</h2>
        <div className={styles.previewBlock}>
          <span className={styles.previewKicker}>Кампания</span>
          <code className={styles.previewName}>{trimmed ? fullName : `${options.prefix}...`}</code>
          <dl className={styles.facts}>
            <dt>Домен</dt>
            <dd>{nameOf(options.domains, domainId)}</dd>
            <dt>Группа</dt>
            <dd>{nameOf(options.groups, groupId)}</dd>
            <dt>Источник</dt>
            <dd>{nameOf(options.traffic_sources, sourceId)}</dd>
            <dt>Ротация</dt>
            <dd>по позиции, CPC 0 USD из параметра cost</dd>
          </dl>
        </div>
        <ol className={styles.flows}>
          <li>
            <span className={styles.flowNumber}>1</span>
            <div>
              <b>Geo {geo.codes.length ? geo.codes.join(', ') : '...'}</b>
              <span className={styles.flowType}>обычный</span>
              <p>
                {geo.codes.length
                  ? `Посетители из стран: ${geo.codes.map(countryName).join(', ')}.`
                  : 'Посетители из выбранных стран.'}{' '}
                Редирект на google.com
              </p>
            </div>
          </li>
          <li>
            <span className={styles.flowNumber}>2</span>
            <div>
              <b>Offers</b>
              <span className={styles.flowType}>замыкающий</span>
              <p>Все остальные. {offer ? `${offerLabel(offer)}, доля 100%` : 'Оффер не выбран'}</p>
            </div>
          </li>
        </ol>
      </aside>
    </div>
  )
}

/** A hint under a field, replaced by the error when there is one */
function FieldMessage({ id, error, children }: { id?: string; error?: string; children?: string }) {
  if (!error && !children) return null
  return (
    <p
      id={id}
      className={cx(styles.hint, error && styles.error)}
      role={error ? 'alert' : undefined}
    >
      {error ?? children}
    </p>
  )
}

function SelectField({
  id,
  label,
  items,
  value,
  onChange,
  error,
}: {
  id: string
  label: string
  items: Named[]
  value: string
  onChange: (value: string) => void
  error?: string
}) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        className="select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error) || undefined}
      >
        {items.length !== 1 && <option value="">Выберите</option>}
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
      <FieldMessage error={error} />
    </div>
  )
}
