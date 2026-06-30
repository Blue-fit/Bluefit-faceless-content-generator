import { BrowserRouter, Routes, Route, useParams, Navigate, Outlet } from 'react-router-dom'
import Header from './components/Header'
import SpendBar from './components/SpendBar'
import HomePage from './pages/HomePage'
import MonthPage from './pages/MonthPage'
import WeekPage from './pages/WeekPage'
import LoginPage from './pages/LoginPage'
import { DataProvider, useData } from './context/DataContext'
import { isAuthed } from './api'
import './App.css'

function MonthPageWrapper() {
  const { monthId } = useParams()
  const { months } = useData()
  const month = months.find(m => m.id === monthId)
  return (
    <>
      <Header monthLabel={month?.label} />
      <SpendBar />
      <MonthPage />
    </>
  )
}

function WeekPageWrapper() {
  const { weekId } = useParams()
  const { weeks } = useData()
  const week = weeks.find(w => w.id === weekId)
  return (
    <>
      <Header weekLabel={week?.label} />
      <SpendBar />
      <WeekPage />
    </>
  )
}

// Gate every app route behind login; shares one DataProvider for the protected tree.
function ProtectedLayout() {
  if (!isAuthed()) return <Navigate to="/login" replace />
  return (
    <DataProvider>
      <div className="app">
        <Outlet />
      </div>
    </DataProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<><Header /><SpendBar /><HomePage /></>} />
          <Route path="/month/:monthId" element={<MonthPageWrapper />} />
          <Route path="/week/:weekId" element={<WeekPageWrapper />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}