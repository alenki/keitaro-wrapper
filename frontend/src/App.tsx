import { Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { CampaignsPage } from './pages/CampaignsPage'
import { NewCampaignPage } from './pages/NewCampaignPage'
import { NotFoundPage } from './pages/NotFoundPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CampaignsPage />} />
        <Route path="campaigns/new" element={<NewCampaignPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
