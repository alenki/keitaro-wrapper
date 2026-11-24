import { Link } from 'react-router'

import { useDocumentTitle } from '../lib/useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Не найдено')
  return (
    <div>
      <h1>Страница не найдена</h1>
      <p>
        <Link to="/">К списку кампаний</Link>
      </p>
    </div>
  )
}
