import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import styles from './ErrorNotice.module.css'

interface Props {
  error: unknown
  action?: ReactNode
}

export function ErrorNotice({ error, action }: Props) {
  const message = error instanceof ApiError ? error.message : 'Что-то пошло не так'
  const requestId = error instanceof ApiError ? error.requestId : null

  return (
    <div className={`alert alert-error ${styles.notice}`} role="alert">
      <div>
        <div>{message}</div>
        {requestId && (
          <div className={styles.requestId}>
            Код запроса для логов: <code>{requestId}</code>
          </div>
        )}
      </div>
      {action}
    </div>
  )
}
