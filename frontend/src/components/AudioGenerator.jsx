import { useState, useRef } from 'react'
import { Music, Zap, Download, Play, Square, RefreshCw, Wand2 } from 'lucide-react'
import axios from 'axios'

const MUSIC_PROMPTS = [
  'Epic orchestral movie soundtrack with drums and strings',
  'Relaxing lofi hip hop beats for studying',
  'Upbeat electronic dance music with synth',
  'Acoustic guitar ballad with soft vocals',
  'Dark ambient cinematic score',
]

const SFX_PROMPTS = [
  'Thunder and lightning storm with heavy rain',
  'Explosion with debris and crackling fire',
  'Crowd cheering in a stadium',
  'Forest ambience with birds and wind',
  'Futuristic robot beeping and mechanical sounds',
]

export default function AudioGenerator({ api }) {
  const [activeType, setActiveType] = useState('music')
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState(10)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef(null)

  const pollTask = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${api}/api/audio/task/${taskId}`)
        const data = res.data
        setProgress(data.progress || 0)
        setStatus(data.status)

        if (data.status === 'completed') {
          clearInterval(interval)
          setResult(data.result)
          setLoading(false)
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setError(data.error || 'Generation failed')
          setLoading(false)
        }
      } catch {
        clearInterval(interval)
        setError('Connection lost')
        setLoading(false)
      }
    }, 2000)
  }

  const generate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    setProgress(0)
    setStatus('queued')

    try {
      const res = await axios.post(`${api}/api/audio/generate`, {
        prompt,
        duration,
        type: activeType,
      })
      pollTask(res.data.task_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start generation')
      setLoading(false)
    }
  }

  const statusLabel = {
    queued: 'Queued...',
    loading_model: `Loading ${activeType === 'music' ? 'MusicGen' : 'AudioGen'} model (first time ~3GB)...`,
    generating: `Generating ${activeType === 'music' ? 'music' : 'sound effects'}...`,
    completed: 'Done!',
    failed: 'Failed',
  }

  const examples = activeType === 'music' ? MUSIC_PROMPTS : SFX_PROMPTS
  const gradient = activeType === 'music' ? 'from-orange-600 to-red-600' : 'from-yellow-600 to-orange-600'

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold gradient-text mb-2">AI Music & Sound Effects</h2>
        <p className="text-white/50">Generate original music and sound effects using Meta's AudioCraft models</p>
      </div>

      {/* Type selector */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={() => { setActiveType('music'); setPrompt('') }}
          className={`flex items-center gap-2 px-5 py-3 rounded-xl font-semibold transition-all ${
            activeType === 'music'
              ? 'bg-gradient-to-r from-orange-600 to-red-600 text-white'
              : 'bg-white/5 text-white/50 hover:bg-white/10'
          }`}
        >
          <Music size={18} /> Music Generator
        </button>
        <button
          onClick={() => { setActiveType('sfx'); setPrompt('') }}
          className={`flex items-center gap-2 px-5 py-3 rounded-xl font-semibold transition-all ${
            activeType === 'sfx'
              ? 'bg-gradient-to-r from-yellow-600 to-orange-600 text-white'
              : 'bg-white/5 text-white/50 hover:bg-white/10'
          }`}
        >
          <Zap size={18} /> Sound Effects
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-5">
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-2">
              Describe your {activeType === 'music' ? 'music' : 'sound effect'}
            </label>
            <textarea
              className="input-field resize-none h-28"
              placeholder={activeType === 'music'
                ? 'Epic orchestral soundtrack with soaring strings...'
                : 'Heavy rain on a metal roof with distant thunder...'}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {examples.map((p, i) => (
                <button key={i} onClick={() => setPrompt(p)}
                  className="text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80 transition-all truncate max-w-[180px]"
                  title={p}>
                  {p.slice(0, 35)}...
                </button>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-white/70">Duration</span>
              <span className="text-orange-400 font-bold">{duration} seconds</span>
            </div>
            <input type="range" min={1} max={30} value={duration}
              onChange={e => setDuration(+e.target.value)} className="w-full accent-orange-500" />
            <p className="text-xs text-white/30 mt-1">
              Longer durations take more time. Max 30 seconds.
            </p>
          </div>

          <div className="card bg-orange-950/20 border-orange-500/20">
            <p className="text-xs text-orange-300/70">
              💡 <strong>Model info:</strong> Uses Meta's MusicGen (music) and AudioGen (SFX).
              First generation downloads ~3GB model. All processing is local and unlimited.
            </p>
          </div>

          <button onClick={generate} disabled={loading || !prompt.trim()}
            className={`w-full py-3 px-6 rounded-xl font-semibold text-white bg-gradient-to-r ${gradient} hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2`}>
            {loading ? (
              <><RefreshCw size={18} className="animate-spin" /> Generating...</>
            ) : (
              <><Wand2 size={18} /> Generate {activeType === 'music' ? 'Music' : 'Sound Effect'}</>
            )}
          </button>

          {loading && (
            <div className="card animate-fade-in">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-white/60">{statusLabel[status] || status}</span>
                <span className="text-orange-400">{progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="h-full rounded-full transition-all duration-300 bg-gradient-to-r from-orange-500 to-red-500"
                  style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {error && (
            <div className="card border-red-500/20 bg-red-500/5">
              <p className="text-red-400 text-sm">❌ {error}</p>
            </div>
          )}
        </div>

        <div>
          {result ? (
            <div className="space-y-4 animate-fade-in">
              <h3 className="text-lg font-semibold text-white">
                Generated {activeType === 'music' ? 'Music' : 'Sound Effect'}
              </h3>
              <div className="card">
                <div className="flex items-center gap-4 mb-4">
                  <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center`}>
                    {activeType === 'music' ? <Music size={28} className="text-white" /> : <Zap size={28} className="text-white" />}
                  </div>
                  <div>
                    <p className="text-white font-medium">{activeType === 'music' ? 'Music Track' : 'Sound Effect'}</p>
                    <p className="text-white/40 text-sm">{duration} seconds · WAV format</p>
                  </div>
                </div>
                <audio
                  ref={audioRef}
                  src={`${api}${result}`}
                  onEnded={() => setPlaying(false)}
                  controls
                  className="w-full"
                  autoPlay
                />
              </div>
              <a href={`${api}${result}`} download
                className="flex items-center justify-center gap-2 py-3 px-6 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-all">
                <Download size={18} /> Download WAV
              </a>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-80 card">
              {activeType === 'music' ? (
                <Music size={48} className="text-white/10 mb-4" />
              ) : (
                <Zap size={48} className="text-white/10 mb-4" />
              )}
              <p className="text-white/30 text-center">
                Your {activeType === 'music' ? 'music track' : 'sound effect'} will appear here
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
