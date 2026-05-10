import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import ImageGenerator from './components/ImageGenerator'
import VideoGenerator from './components/VideoGenerator'
import VoiceGenerator from './components/VoiceGenerator'
import AudioGenerator from './components/AudioGenerator'
import Gallery from './components/Gallery'
import { Sparkles } from 'lucide-react'

const API = 'http://localhost:8000'

export default function App() {
  const [activeTab, setActiveTab] = useState('images')
  const [backendStatus, setBackendStatus] = useState('checking')

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API}/api/health`)
        if (res.ok) setBackendStatus('online')
        else setBackendStatus('offline')
      } catch {
        setBackendStatus('offline')
      }
    }
    check()
    const interval = setInterval(check, 10000)
    return () => clearInterval(interval)
  }, [])

  const renderContent = () => {
    switch (activeTab) {
      case 'images': return <ImageGenerator api={API} />
      case 'videos': return <VideoGenerator api={API} />
      case 'voice': return <VoiceGenerator api={API} />
      case 'audio': return <AudioGenerator api={API} />
      case 'gallery': return <Gallery api={API} />
      default: return <ImageGenerator api={API} />
    }
  }

  return (
    <div className="flex h-screen bg-[#0a0a12] overflow-hidden">
      {/* Ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-900/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-900/20 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-pink-900/10 rounded-full blur-3xl" />
      </div>

      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="flex-1 flex flex-col min-h-0 relative">
        {/* Header */}
        <header className="flex items-center justify-between px-8 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-purple-600 to-blue-600">
              <Sparkles size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text">AI Creative Studio</h1>
              <p className="text-xs text-white/40">Unlimited free AI generation</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm">
              <span className={`w-2 h-2 rounded-full ${backendStatus === 'online' ? 'bg-green-400' : backendStatus === 'checking' ? 'bg-yellow-400 animate-pulse' : 'bg-red-400'}`} />
              <span className="text-white/50">
                {backendStatus === 'online' ? 'AI Engine Online' : backendStatus === 'checking' ? 'Connecting...' : 'Engine Offline — start backend'}
              </span>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-8">
          {backendStatus === 'offline' ? (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <div className="card text-center max-w-md">
                <div className="text-4xl mb-4">⚠️</div>
                <h2 className="text-xl font-bold text-white mb-2">Backend Not Running</h2>
                <p className="text-white/50 text-sm mb-4">
                  Start the AI backend first, then refresh this page.
                </p>
                <div className="bg-black/30 rounded-lg p-3 text-left font-mono text-xs text-green-400">
                  cd ai-creative-studio\backend<br />
                  python main.py
                </div>
              </div>
            </div>
          ) : (
            <div className="animate-fade-in">{renderContent()}</div>
          )}
        </main>
      </div>
    </div>
  )
}
