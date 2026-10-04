import { Route, Routes } from 'react-router-dom'
import { BitcoinPage } from './features/bitcoin/BitcoinPage'
import { AppShell } from './components/AppShell'
import { AnalyzerHome } from './features/analyzer/AnalyzerHome'
import { AnalyzerPage } from './features/analyzer/AnalyzerPage'
import { ResearchPage } from './features/research/ResearchPage'
import { InsightsPage } from './features/simulations/InsightsPage'
import { SimulationDetail } from './features/simulations/SimulationDetail'
import { SimulationsPage } from './features/simulations/SimulationsPage'
import { SettingsPage, StatusPage } from './features/status/StatusPages'
import { HelpPage } from './features/help/HelpPage'
import { RoutinePage } from './features/routine/RoutinePage'
import { WatchlistPage } from './features/watchlist/WatchlistPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<AnalyzerHome />} />
        <Route path="analyzer/:id" element={<AnalyzerPage />} />
        <Route path="bitcoin" element={<BitcoinPage />} />
        <Route path="bitcoin/:page" element={<BitcoinPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="research" element={<ResearchPage />} />
        <Route path="simulations" element={<SimulationsPage />} />
        <Route path="simulations/insights" element={<InsightsPage />} />
        <Route path="simulations/:id" element={<SimulationDetail />} />
        <Route path="rutina" element={<RoutinePage />} />
        <Route path="ayuda" element={<HelpPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<AnalyzerHome />} />
      </Route>
    </Routes>
  )
}
