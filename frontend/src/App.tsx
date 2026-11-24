import { Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { CampaignsPage } from './pages/CampaignsPage'
import { NotFoundPage } from './pages/NotFoundPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CampaignsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
