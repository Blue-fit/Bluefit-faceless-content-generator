import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import SpendBar from './components/SpendBar'
import HomePage from './pages/HomePage'
import WeekPage from './pages/WeekPage'
import { WEEKS } from './data'
import { useParams } from 'react-router-dom'
import './App.css'

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
          <Route path="/week/:weekId" element={<WeekPageWrapper />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
