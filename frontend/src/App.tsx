import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { AnalyzerHome } from './features/analyzer/AnalyzerHome'
import { AnalyzerPage } from './features/analyzer/AnalyzerPage'
import { ResearchPage } from './features/research/ResearchPage'
import { SettingsPage, StatusPage } from './features/status/StatusPages'
import { WatchlistPage } from './features/watchlist/WatchlistPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<AnalyzerHome />} />
        <Route path="analyzer/:id" element={<AnalyzerPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="research" element={<ResearchPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<AnalyzerHome />} />
      </Route>
    </Routes>
  )
}
