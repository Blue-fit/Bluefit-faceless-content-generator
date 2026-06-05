import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'
import Header from './components/Header'
import SpendBar from './components/SpendBar'
import HomePage from './pages/HomePage'
import MonthPage from './pages/MonthPage'
import WeekPage from './pages/WeekPage'
import { MONTHS, WEEKS } from './data'
import './App.css'

function MonthPageWrapper() {
  const { monthId } = useParams()
  const month = MONTHS.find(m => m.id === monthId)
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
  const week = WEEKS.find(w => w.id === weekId)
  return (
    <>
      <Header weekLabel={week?.label} />
      <SpendBar />
      <WeekPage />
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={
            <>
              <Header />
              <SpendBar />
              <HomePage />
            </>
          } />
          <Route path="/month/:monthId" element={<MonthPageWrapper />} />
          <Route path="/week/:weekId" element={<WeekPageWrapper />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
