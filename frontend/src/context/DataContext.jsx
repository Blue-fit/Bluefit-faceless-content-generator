import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { fetchWeeks } from '../api'

const DataContext = createContext(null)

export function DataProvider({ children }) {
  const [months, setMonths] = useState([])
  const [weeks, setWeeks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchWeeks()
      setMonths(data.months)
      setWeeks(data.weeks)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <DataContext.Provider value={{ months, weeks, loading, error, refresh: load }}>
      {children}
    </DataContext.Provider>
  )
}

export function useData() {
  return useContext(DataContext)
}
