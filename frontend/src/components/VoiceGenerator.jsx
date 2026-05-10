import { useState, useEffect, useRef } from 'react'
import { Mic, Download, Play, Square, RefreshCw } from 'lucide-react'
import axios from 'axios'

const SAMPLE_TEXTS = [
  'Welcome to AI Creative Studio! Create stunning content with the power of artificial intelligence.',
  'The quick brown fox jumps over the lazy dog.',
  'In a world of endless possibilities, creativity knows no bounds.',
  'Hello everyone! Today we are going to explore the amazing capabilities of AI voice generation.',
]

export default function VoiceGenerator({ api }) {
  const [text, setText] = useState('')
  const [voices, setVoices] = useState([])
  const [selectedVoice, setSelectedVoice] = useState('en-US-JennyNeural')
  const [rate, setRate] = useState(0)
  const [pitch, setPitch] = useState(0)
  const [volume, setVolume] = useState(0)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [playing, setPlaying] = useState(false)
  const [searchVoice, setSearchVoice] = useState('')
  const audioRef = useRef(null)

  useEffect(() => {
    axios.get(`${api}/api/voice/voices`).then(res => {
      setVoices(res.data.voices || [])
    }).catch(() => {})
  }, [api])

  const filteredVoices = voices.filter(v =>
    v.display.toLowerCase().includes(searchVoice.toLowerCase()) ||
    v.locale.toLowerCase().includes(searchVoice.toLowerCase())
  )

  const generate = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await axios.post(`${api}/api/voice/generate`, {
        text,
        voice: selectedVoice,
        rate: `${rate >= 0 ? '+' : ''}${rate}%`,
        pitch: `${pitch >= 0 ? '+' : ''}${pitch}Hz`,
        volume: `${volume >= 0 ? '+' : ''}${volume}%`,
      })
      setResult(res.data.result)
    } catch (e) {
      setError(e.response?.data?.detail || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) {
      audioRef.current.pause()
      setPlaying(false)
    } else {
      audioRef.current.play()
      setPlaying(true)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold gradient-text mb-2">AI Voice Over</h2>
        <p className="text-white/50">Convert text to natural speech with 400+ voices in 100+ languages — completely free</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-5">
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-2">
              Your text <span className="text-white/30">({text.length} chars)</span>
            </label>
            <textarea
              className="input-field resize-none h-36"
              placeholder="Enter the text you want to convert to speech..."
              value={text}
              onChange={e => setText(e.target.value)}
            />
            <div className="mt-2 flex flex-wrap gap-2">
              {SAMPLE_TEXTS.map((t, i) => (
                <button key={i} onClick={() => setText(t)}
                  className="text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80 transition-all">
                  Sample {i + 1}
                </button>
              ))}
            </div>
          </div>

          {/* Voice selector */}
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-2">Voice ({voices.length} available)</label>
            <input
              type="text"
              className="input-field text-sm mb-2"
              placeholder="Search voices by name or language..."
              value={searchVoice}
              onChange={e => setSearchVoice(e.target.value)}
            />
            <div className="max-h-40 overflow-y-auto space-y-1">
              {filteredVoices.slice(0, 50).map(v => (
                <button
                  key={v.name}
                  onClick={() => setSelectedVoice(v.display)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all ${
                    selectedVoice === v.display
                      ? 'bg-green-600/30 border border-green-500/30 text-white'
                      : 'bg-white/[0.03] hover:bg-white/[0.07] text-white/60'
                  }`}
                >
                  <span>{v.display}</span>
                  <span className="text-xs text-white/30">{v.gender} · {v.locale}</span>
                </button>
              ))}
              {filteredVoices.length === 0 && (
                <p className="text-white/30 text-sm text-center py-4">No voices found</p>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="card space-y-4">
            <h4 className="text-sm font-medium text-white/70">Voice Settings</h4>
            <div>
              <div className="flex justify-between text-xs text-white/50 mb-1">
                <span>Speed</span>
                <span className="text-green-400">{rate >= 0 ? '+' : ''}{rate}%</span>
              </div>
              <input type="range" min={-50} max={100} step={5} value={rate}
                onChange={e => setRate(+e.target.value)} className="w-full accent-green-500" />
            </div>
            <div>
              <div className="flex justify-between text-xs text-white/50 mb-1">
                <span>Pitch</span>
                <span className="text-green-400">{pitch >= 0 ? '+' : ''}{pitch}Hz</span>
              </div>
              <input type="range" min={-50} max={50} step={5} value={pitch}
                onChange={e => setPitch(+e.target.value)} className="w-full accent-green-500" />
            </div>
            <div>
              <div className="flex justify-between text-xs text-white/50 mb-1">
                <span>Volume</span>
                <span className="text-green-400">{volume >= 0 ? '+' : ''}{volume}%</span>
              </div>
              <input type="range" min={-50} max={50} step={5} value={volume}
                onChange={e => setVolume(+e.target.value)} className="w-full accent-green-500" />
            </div>
          </div>

          <button onClick={generate} disabled={loading || !text.trim()}
            className="w-full py-3 px-6 rounded-xl font-semibold text-white bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-500 hover:to-teal-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
            {loading ? (
              <><RefreshCw size={18} className="animate-spin" /> Generating...</>
            ) : (
              <><Mic size={18} /> Generate Voice</>
            )}
          </button>

          {error && (
            <div className="card border-red-500/20 bg-red-500/5">
              <p className="text-red-400 text-sm">❌ {error}</p>
            </div>
          )}
        </div>

        <div>
          {result ? (
            <div className="space-y-4 animate-fade-in">
              <h3 className="text-lg font-semibold text-white">Generated Voice</h3>
              <div className="card">
                <div className="flex items-center gap-4 mb-4">
                  <button onClick={togglePlay}
                    className="w-14 h-14 rounded-full bg-gradient-to-br from-green-500 to-teal-500 flex items-center justify-center hover:opacity-90 transition-opacity">
                    {playing ? <Square size={20} className="text-white" /> : <Play size={20} className="text-white ml-1" />}
                  </button>
                  <div>
                    <p className="text-white font-medium">Voice Over Ready</p>
                    <p className="text-white/40 text-sm">{selectedVoice}</p>
                  </div>
                </div>
                <audio
                  ref={audioRef}
                  src={`${api}${result}`}
                  onEnded={() => setPlaying(false)}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  controls
                  className="w-full"
                />
              </div>
              <a href={`${api}${result}`} download
                className="flex items-center justify-center gap-2 py-3 px-6 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-all">
                <Download size={18} /> Download MP3
              </a>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-80 card">
              <Mic size={48} className="text-white/10 mb-4" />
              <p className="text-white/30 text-center">Your generated voice will appear here</p>
              <p className="text-white/20 text-sm mt-2">Instant generation, no model download needed</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
