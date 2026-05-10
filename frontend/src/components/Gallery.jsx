import { useState, useEffect } from 'react'
import { Grid, Image, Video, Mic, Music, Download, RefreshCw, Trash2 } from 'lucide-react'
import axios from 'axios'

const TYPE_ICONS = {
  images: Image,
  videos: Video,
  voice: Mic,
  audio: Music,
}

const TYPE_COLORS = {
  images: 'from-purple-500 to-pink-500',
  videos: 'from-blue-500 to-cyan-500',
  voice: 'from-green-500 to-teal-500',
  audio: 'from-orange-500 to-red-500',
}

export default function Gallery({ api }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const load = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${api}/api/gallery`)
      setItems(res.data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = filter === 'all' ? items : items.filter(i => i.type === filter)

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / 1024 / 1024).toFixed(1)}MB`
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-3xl font-bold gradient-text mb-2">Your Gallery</h2>
          <p className="text-white/50">{items.length} creations · All generated locally on your machine</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/70 text-sm transition-all">
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {['all', 'images', 'videos', 'voice', 'audio'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all capitalize ${
              filter === f
                ? 'bg-white/15 text-white border border-white/20'
                : 'bg-white/5 text-white/50 hover:bg-white/10'
            }`}
          >
            {f === 'all' ? `All (${items.length})` : `${f.charAt(0).toUpperCase() + f.slice(1)} (${items.filter(i => i.type === f).length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-square rounded-2xl bg-white/5 shimmer" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 card">
          <Grid size={48} className="text-white/10 mb-4" />
          <p className="text-white/30">No creations yet. Start generating!</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map((item, i) => {
            const Icon = TYPE_ICONS[item.type] || Grid
            const gradient = TYPE_COLORS[item.type] || 'from-gray-500 to-gray-600'
            const isMedia = item.type === 'images' || item.type === 'videos'

            return (
              <div key={i} className="group relative rounded-2xl overflow-hidden border border-white/10 bg-white/[0.03] hover:border-white/20 transition-all">
                {item.type === 'images' ? (
                  <img src={`${api}${item.url}`} alt={item.filename}
                    className="w-full aspect-square object-cover" />
                ) : item.type === 'videos' ? (
                  <video src={`${api}${item.url}`} className="w-full aspect-square object-cover" muted />
                ) : (
                  <div className={`w-full aspect-square flex flex-col items-center justify-center bg-gradient-to-br ${gradient} opacity-20`}>
                    <Icon size={40} className="text-white mb-2" />
                  </div>
                )}

                {/* Overlay */}
                <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-3 p-3">
                  {(item.type === 'voice' || item.type === 'audio') && (
                    <audio src={`${api}${item.url}`} controls className="w-full" />
                  )}
                  <a href={`${api}${item.url}`} download
                    className="flex items-center gap-2 bg-white/20 hover:bg-white/30 backdrop-blur px-3 py-2 rounded-xl text-white text-sm font-medium transition-all w-full justify-center">
                    <Download size={14} /> Download
                  </a>
                </div>

                {/* Type badge */}
                <div className="absolute top-2 left-2">
                  <div className={`flex items-center gap-1 px-2 py-0.5 rounded-lg bg-gradient-to-r ${gradient} text-white text-xs font-medium opacity-90`}>
                    <Icon size={10} />
                    {item.type}
                  </div>
                </div>

                {/* Size badge */}
                <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="text-xs bg-black/60 px-2 py-0.5 rounded-lg text-white/60">
                    {formatSize(item.size)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
