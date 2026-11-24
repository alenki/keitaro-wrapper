const dateTime = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : dateTime.format(date)
}

/** Keitaro sends times like "2026-11-24 09:37:20" in UTC */
export function formatKeitaroTime(value: string | null): string {
  if (!value) return ''
  return formatTime(`${value.replace(' ', 'T')}Z`)
}
