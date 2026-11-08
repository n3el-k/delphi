import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from '@/components/Layout'
import DashboardPage from '@/pages/DashboardPage'
import GatePage from '@/pages/GatePage'
import NewProjectPage from '@/pages/NewProjectPage'
import NotFoundPage from '@/pages/NotFoundPage'
import PortfolioPage from '@/pages/PortfolioPage'

/** Which page shows at which address. Every page sits inside Layout (nav + main). */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects/new" element={<NewProjectPage />} />
          {/* The bot's PR comment links here: backend/app/routers/webhooks.py builds the URL */}
          <Route path="/gates/:id" element={<GatePage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
