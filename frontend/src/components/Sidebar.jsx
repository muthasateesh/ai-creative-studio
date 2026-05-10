import { Image, Video, Mic, Music, Grid, Sparkles } from 'lucide-react'

const tabs = [
  { id: 'images', label: 'AI Images', icon: Image, color: 'from-purple-500 to-pink-500', desc: 'Text to image' },
  { id: 'videos', label: 'AI Videos', icon: Video, color: 'from-blue-500 to-cyan-500', desc: 'Text to video' },
  { id: 'voice', label: 'Voice Over', icon: Mic, color: 'from-green-500 to-teal-500', desc: 'Text to speech' },
  { id: 'audio', label: 'Music & SFX', icon: Music, color: 'from-orange-500 to-red-500', desc: 'AI audio' },
  { id: 'gallery', label: 'Gallery', icon: Grid, color: 'from-indigo-500 to-purple-500', desc: 'Your creations' },
]

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="w-64 flex flex-col border-r border-white/[0.06] bg-white/[0.02] relative z-10">
      {/* Logo */}
      <div className="p-6 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-purple-600 via-blue-600 to-pink-600 flex items-center justify-center glow-purple">
            <Sparkles size={20} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">AI Creative</div>
            <div className="text-xs text-white/40">Studio Pro</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <div className="text-xs font-semibold text-white/30 uppercase tracking-wider mb-3 px-2">
          Create
        </div>
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group ${
                isActive
                  ? 'bg-white/10 border border-white/10'
                  : 'hover:bg-white/5 border border-transparent'
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-to-br ${tab.color} ${isActive ? 'opacity-100' : 'opacity-60 group-hover:opacity-80'} transition-opacity`}>
                <Icon size={16} className="text-white" />
              </div>
              <div className="text-left">
                <div className={`text-sm font-medium ${isActive ? 'text-white' : 'text-white/60 group-hover:text-white/80'}`}>
                  {tab.label}
                </div>
                <div className="text-xs text-white/30">{tab.desc}</div>
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-purple-400" />
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/[0.06]">
        <div className="card !p-3 text-center">
          <div className="text-xs text-white/40 mb-1">Powered by</div>
          <div className="text-xs font-semibold text-white/60">
            Stable Diffusion · MusicGen<br />
            Edge TTS · Zeroscope
          </div>
          <div className="mt-2 text-xs text-green-400/70">100% Free & Unlimited</div>
        </div>
      </div>
    </aside>
  )
}
