import { Dashboard } from './components/Dashboard'
import { ToastProvider } from './context/ToastContext'
import { ToastViewport } from './components/common/ToastViewport'

function App() {
  return (
    <ToastProvider>
      <Dashboard />
      <ToastViewport />
    </ToastProvider>
  )
}

export default App
