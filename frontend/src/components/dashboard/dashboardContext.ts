import { useOutletContext } from 'react-router-dom'

export interface DashboardOutletContext {
  searchQuery: string
  setSearchQuery: (value: string) => void
}

export function useDashboardContext() {
  return useOutletContext<DashboardOutletContext>()
}
