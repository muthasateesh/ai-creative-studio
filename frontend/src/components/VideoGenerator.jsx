import { useState, useEffect, useRef } from 'react'
import { Download, Wand2, Mic, Music2, Volume2, ChevronDown, ChevronUp, Play, RotateCcw, Sparkles } from 'lucide-react'
import axios from 'axios'

const EXAMPLE_PROMPTS = [
  'A rocket launches through storm clouds into deep space',
  'Ocean waves crashing on rocks at golden hour',
  'City skyline at night with neon reflections in the rain',
  'Snow falls silently through an ancient enchanted forest',
  'Abstract color waves flow like liquid light',
  'A glowing fantasy portal in a misty mountain valley',
]

const ASPECT_RATIOS = [
  { id: '16:9',  label: '16:9',  w: 1280, h: 720,  icon: '▬' },
  { id: '9:16',  label: '9:16',  w: 720,  h: 1280, icon: '▮' },
  { id: '1:1',   label: '1:1',   w: 720,  h: 720,  icon: '■' },
]

const QUALITY = [
  { id: '480p',  label: '480p',  scale: 0.667 },
  { id: '720p',  label: '720p',  scale: 1.0   },
  { id: '1080p', label: '1080p', scale: 1.5   },
]

const MUSIC_STYLES = {
  auto: '✨ Auto', upbeat: '🎵 Upbeat', calm: '🌿 Calm',
  epic: '⚔️ Epic', cinematic: '🎞️ Cinematic', electronic: '🎛️ Electronic', jazz: '🎷 Jazz',
}

const PIPELINE = ['rendering', 'generating voice', 'composing music', 'mixing audio']
const STATUS_LABEL = {
  queued: 'Queued…', rendering: 'Rendering frames…',
  'generating voice': 'Generating voice…', 'composing music': 'Composing music…',
  'mixing audio': 'Mixing audio…', completed: 'Done!', failed: 'Failed',
}

const AUTO_AGENT = { id: 'auto', name: 'Auto', emoji: '🤖', desc: 'Detects scene from prompt' }

export default function VideoGenerator({ api }) {
  const [agents,       setAgents]       = useState([])
  const [activeAgent,  setActiveAgent]  = useState('auto')
  const [voices,       setVoices]       = useState([])
  const [voiceSearch,  setVoiceSearch]  = useState('')

  const [prompt,       setPrompt]       = useState('')
  const [aspectRatio,  setAspectRatio]  = useState('16:9')
  const [quality,      setQuality]      = useState('720p')
  const [numFrames,    setNumFrames]    = useState(240)
  const [fps,          setFps]          = useState(24)

  const [voiceEnabled,  setVoiceEnabled]  = useState(false)
  const [usePromptText, setUsePromptText] = useState(true)
  const [voiceCustom,   setVoiceCustom]   = useState('')
  const [voiceName,     setVoiceName]     = useState('en-US-AriaNeural')
  const [voiceRate,     setVoiceRate]     = useState(0)
  const [voicePitch,    setVoicePitch]    = useState(0)
  const [musicEnabled,  setMusicEnabled]  = useState(true)
  const [musicStyle,    setMusicStyle]    = useState('auto')
  const [musicVolume,   setMusicVolume]   = useState(30)

  const [showAudioAdv,  setShowAudioAdv]  = useState(false)
  const [showVoiceAdv,  setShowVoiceAdv]  = useState(false)

  const [loading,  setLoading]  = useState(false)
  const [progress, setProgress] = useState(0)
  const [status,   setStatus]   = useState('')
  const [scene,    setScene]    = useState('')
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState('')

  const videoRef = useRef(null)

  useEffect(() => {
    axios.get(`${api}/api/videos/agents`).then(r => setAgents(r.data.agents || [])).catch(() => {})
    fetch(`${api}/api/voice/voices`).then(r => r.json()).then(d => setVoices(d.voices || [])).catch(() => {})
  }, [api])

  const filteredVoices = voices.filter(v =>
    v.ShortName?.toLowerCase().includes(voiceSearch.toLowerCase()) ||
    v.FriendlyName?.toLowerCase().includes(voiceSearch.toLowerCase())
  )

  // compute W×H from aspect ratio + quality
  const getDims = () => {
    const ar = ASPECT_RATIOS.find(a => a.id === aspectRatio) || ASPECT_RATIOS[0]
    const q  = QUALITY.find(q => q.id === quality) || QUALITY[1]
    return { w: Math.round(ar.w * q.scale / 2) * 2, h: Math.round(ar.h * q.scale / 2) * 2 }
  }

  const pollTask = (taskId) => {
    const iv = setInterval(async () => {
      try {
        const { data } = await axios.get(`${api}/api/videos/task/${taskId}`)
        setProgress(data.progress || 0)
        setStatus(data.status)
        if (data.scene) setScene(data.scene)
        if (data.status === 'completed') {
          clearInterval(iv); setResult(data.result); setLoading(false)
        } else if (data.status === 'failed') {
          clearInterval(iv); setError(data.error || 'Generation failed'); setLoading(false)
        }
      } catch { clearInterval(iv); setError('Connection lost'); setLoading(false) }
    }, 1000)
  }

  const generate = async () => {
    if (!prompt.trim()) return
    setLoading(true); setError(''); setResult(null); setProgress(0)
    setStatus('queued'); setScene('')
    try {
      const { w, h } = getDims()
      const { data } = await axios.post(`${api}/api/videos/generate`, {
        prompt,
        num_frames:      numFrames,
        fps,
        width:  w,
        height: h,
        agent:           activeAgent,
        camera_movement: 'auto',
        voice_enabled:   voiceEnabled,
        voice_text:      voiceEnabled && !usePromptText ? voiceCustom : '',
        voice_name:      voiceName,
        voice_rate:      `${voiceRate >= 0 ? '+' : ''}${voiceRate}%`,
        voice_pitch:     `${voicePitch >= 0 ? '+' : ''}${voicePitch}Hz`,
        music_enabled:   musicEnabled,
        music_style:     musicStyle,
        music_volume:    musicVolume / 100,
      })
      pollTask(data.task_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start')
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null); setProgress(0); setStatus(''); setScene(''); setError('')
  }

  const pipelineIdx = PIPELINE.indexOf(status)
  const allAgents   = [AUTO_AGENT, ...agents]
  const { w: dimW, h: dimH } = getDims()

  return (
    <div className="max-w-7xl mx-auto space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold gradient-text">AI Video Generator</h2>
          <p className="text-white/40 text-sm mt-0.5">Choose an agent · Describe · Generate</p>
        </div>
        {result && (
          <button onClick={reset}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/60 text-sm transition-all">
            <RotateCcw size={14} /> New Video
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-6">

        {/* ── Left column ── */}
        <div className="space-y-4">

          {/* Agent selector */}
          <div className="card !p-5">
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">Choose Agent</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {allAgents.map(ag => (
                <button key={ag.id} onClick={() => setActiveAgent(ag.id)}
                  className={`relative flex flex-col items-center gap-1.5 p-3 rounded-2xl border transition-all text-center
                    ${activeAgent === ag.id
                      ? 'border-purple-500/70 bg-purple-600/20 shadow-[0_0_16px_rgba(147,51,234,0.3)]'
                      : 'border-white/[0.07] bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]'}`}>
                  <span className="text-2xl leading-none">{ag.emoji}</span>
                  <span className={`text-xs font-bold ${activeAgent === ag.id ? 'text-purple-300' : 'text-white/70'}`}>
                    {ag.name}
                  </span>
                  <span className="text-[10px] text-white/35 leading-tight">{ag.desc}</span>
                  {activeAgent === ag.id && (
                    <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-purple-400" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Prompt */}
          <div className="card !p-5">
            <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">
              Describe your video
            </label>
            <textarea
              className="input-field resize-none w-full h-28 text-sm"
              placeholder="A rocket launches through storm clouds into deep space, cinematic lighting…"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) generate() }}
            />
            <div className="mt-3 flex flex-wrap gap-1.5">
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button key={i} onClick={() => setPrompt(p)}
                  className="text-xs px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.09] text-white/40 hover:text-white/70 transition-all truncate max-w-[200px]"
                  title={p}>{p.slice(0, 36)}…</button>
              ))}
            </div>
          </div>

          {/* Video settings */}
          <div className="card !p-5 space-y-4">
            {/* Aspect ratio */}
            <div>
              <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Aspect Ratio</p>
              <div className="flex gap-2">
                {ASPECT_RATIOS.map(ar => (
                  <button key={ar.id} onClick={() => setAspectRatio(ar.id)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold border transition-all
                      ${aspectRatio === ar.id
                        ? 'bg-blue-600/30 border-blue-500/60 text-blue-300'
                        : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                    <span className="text-xs opacity-70">{ar.icon}</span> {ar.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Quality */}
            <div>
              <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Quality</p>
              <div className="flex gap-2">
                {QUALITY.map(q => (
                  <button key={q.id} onClick={() => setQuality(q.id)}
                    className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all
                      ${quality === q.id
                        ? 'bg-blue-600/30 border-blue-500/60 text-blue-300'
                        : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                    {q.label}
                    <span className="block text-[10px] opacity-50 mt-0.5">
                      {Math.round(ASPECT_RATIOS.find(a=>a.id===aspectRatio)?.w*q.scale||0)}×{Math.round(ASPECT_RATIOS.find(a=>a.id===aspectRatio)?.h*q.scale||0)}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Duration + FPS */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-white/40 font-semibold uppercase tracking-wider">Duration</span>
                  <span className="text-blue-400 font-bold">{(numFrames/fps).toFixed(0)}s</span>
                </div>
                <input type="range" min={24} max={720} step={24} value={numFrames}
                  onChange={e => setNumFrames(+e.target.value)} className="w-full accent-blue-500" />
                <div className="flex justify-between text-[10px] text-white/20 mt-1">
                  <span>1s</span><span>30s</span>
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-1.5">FPS</p>
                <div className="flex gap-1.5">
                  {[12, 24, 30].map(f => (
                    <button key={f} onClick={() => setFps(f)}
                      className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all
                        ${fps === f ? 'bg-blue-600/30 border-blue-500/60 text-blue-300' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Music */}
          <div className="card !p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Music2 size={14} className="text-orange-400" />
                <span className="text-sm font-semibold text-white/70">Background Music</span>
              </div>
              <button onClick={() => setMusicEnabled(v => !v)}
                className={`relative w-10 h-5 rounded-full transition-colors ${musicEnabled ? 'bg-orange-500' : 'bg-white/10'}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${musicEnabled ? 'left-5' : 'left-0.5'}`} />
              </button>
            </div>
            {musicEnabled && (
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-1.5">
                  {Object.entries(MUSIC_STYLES).map(([id, label]) => (
                    <button key={id} onClick={() => setMusicStyle(id)}
                      className={`px-2 py-1.5 rounded-xl text-[11px] font-medium border transition-all text-center
                        ${musicStyle === id ? 'bg-orange-600/30 border-orange-500/60 text-white' : 'bg-white/[0.03] border-white/[0.06] text-white/45 hover:text-white/75'}`}>
                      {label}
                    </button>
                  ))}
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-white/40 flex items-center gap-1"><Volume2 size={10}/> Volume</span>
                    <span className="text-white/60">{musicVolume}%</span>
                  </div>
                  <input type="range" min={5} max={80} value={musicVolume}
                    onChange={e => setMusicVolume(+e.target.value)} className="w-full accent-orange-500" />
                </div>
              </div>
            )}
          </div>

          {/* Voice */}
          <div className="card !p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mic size={14} className="text-green-400" />
                <span className="text-sm font-semibold text-white/70">Voice Narration</span>
              </div>
              <button onClick={() => setVoiceEnabled(v => !v)}
                className={`relative w-10 h-5 rounded-full transition-colors ${voiceEnabled ? 'bg-green-500' : 'bg-white/10'}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${voiceEnabled ? 'left-5' : 'left-0.5'}`} />
              </button>
            </div>
            {voiceEnabled && (
              <div className="space-y-3">
                <div className="flex rounded-xl overflow-hidden border border-white/[0.06]">
                  {[true, false].map((isPrompt, idx) => (
                    <button key={idx} onClick={() => setUsePromptText(isPrompt)}
                      className={`flex-1 py-1.5 text-xs font-semibold transition-all
                        ${usePromptText === isPrompt ? 'bg-green-600/30 text-green-300' : 'bg-white/[0.03] text-white/40 hover:text-white/70'}`}>
                      {isPrompt ? 'Read prompt' : 'Custom text'}
                    </button>
                  ))}
                </div>
                {!usePromptText && (
                  <textarea className="input-field resize-none w-full h-16 text-xs"
                    placeholder="Enter custom narration text…"
                    value={voiceCustom} onChange={e => setVoiceCustom(e.target.value)} />
                )}
                <button onClick={() => setShowVoiceAdv(v => !v)}
                  className="flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors">
                  {showVoiceAdv ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
                  Voice settings
                </button>
                {showVoiceAdv && (
                  <div className="space-y-3 pt-1">
                    <input className="input-field w-full text-xs py-1.5" placeholder="Search voices…"
                      value={voiceSearch} onChange={e => setVoiceSearch(e.target.value)} />
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {filteredVoices.slice(0, 40).map((v, i) => (
                        <button key={i} onClick={() => setVoiceName(v.ShortName)}
                          className={`w-full text-left px-3 py-1.5 rounded-lg text-xs transition-all
                            ${voiceName === v.ShortName ? 'bg-green-600/25 text-green-300' : 'hover:bg-white/5 text-white/50'}`}>
                          {v.FriendlyName || v.ShortName}
                        </button>
                      ))}
                    </div>
                    {[['Rate', voiceRate, setVoiceRate, -50, 100, '%'], ['Pitch', voicePitch, setVoicePitch, -20, 20, 'Hz']].map(([label, val, set, min, max, unit]) => (
                      <div key={label}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-white/40">{label}</span>
                          <span className="text-white/60">{val >= 0 ? '+' : ''}{val}{unit}</span>
                        </div>
                        <input type="range" min={min} max={max} value={val}
                          onChange={e => set(+e.target.value)} className="w-full accent-green-500" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Generate */}
          <button onClick={generate} disabled={loading || !prompt.trim()}
            className="w-full py-4 rounded-2xl font-bold text-base transition-all flex items-center justify-center gap-3
              bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500
              disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-purple-900/30">
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Generate Video
                <span className="text-white/50 text-sm font-normal">Ctrl+Enter</span>
              </>
            )}
          </button>
        </div>

        {/* ── Right column: output ── */}
        <div className="space-y-4">

          {/* Preview / result area */}
          <div className={`card !p-0 overflow-hidden ${aspectRatio === '9:16' ? 'max-w-[260px] mx-auto' : ''}`}
            style={{ aspectRatio: aspectRatio === '9:16' ? '9/16' : aspectRatio === '1:1' ? '1/1' : '16/9' }}>
            {result ? (
              <video ref={videoRef} src={`${api}${result}`} controls autoPlay loop
                className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-purple-900/20 to-blue-900/20">
                {loading ? (
                  <div className="text-center px-6">
                    {/* Progress ring */}
                    <div className="relative w-20 h-20 mx-auto mb-4">
                      <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                        <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6"/>
                        <circle cx="40" cy="40" r="34" fill="none" stroke="url(#pg)" strokeWidth="6"
                          strokeLinecap="round"
                          strokeDasharray={`${2*Math.PI*34}`}
                          strokeDashoffset={`${2*Math.PI*34*(1-progress/100)}`}
                          style={{transition:'stroke-dashoffset 0.5s ease'}}/>
                        <defs>
                          <linearGradient id="pg" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#a855f7"/>
                            <stop offset="100%" stopColor="#3b82f6"/>
                          </linearGradient>
                        </defs>
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm">
                        {progress}%
                      </span>
                    </div>
                    <p className="text-white/70 text-sm font-medium">{STATUS_LABEL[status] || 'Working…'}</p>

                    {/* Pipeline pills */}
                    <div className="flex flex-wrap justify-center gap-1.5 mt-4">
                      {PIPELINE.map((stage, idx) => (
                        <span key={stage}
                          className={`px-2.5 py-1 rounded-full text-[10px] font-semibold transition-all
                            ${idx < pipelineIdx   ? 'bg-green-600/30 text-green-400 border border-green-500/30'
                            : idx === pipelineIdx  ? 'bg-purple-600/40 text-purple-300 border border-purple-500/40 animate-pulse'
                            :                        'bg-white/5 text-white/20 border border-white/[0.05]'}`}>
                          {idx < pipelineIdx ? '✓ ' : ''}{stage}
                        </span>
                      ))}
                    </div>

                    {scene && (
                      <div className="mt-3 text-[11px] text-white/30">
                        Scene: <span className="text-purple-400">{scene}</span>
                        {activeAgent !== 'auto' && <> · Agent: <span className="text-blue-400">{activeAgent}</span></>}
                      </div>
                    )}
                  </div>
                ) : error ? (
                  <div className="text-center px-6">
                    <div className="text-3xl mb-3">⚠️</div>
                    <p className="text-red-400 text-sm font-medium">{error}</p>
                    <button onClick={generate} className="mt-4 px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 text-sm transition-all">
                      Retry
                    </button>
                  </div>
                ) : (
                  <div className="text-center px-6">
                    <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mx-auto mb-3">
                      <Play size={28} className="text-white/20 ml-1" />
                    </div>
                    <p className="text-white/20 text-sm">Your video will appear here</p>
                    <p className="text-white/10 text-xs mt-1">{dimW}×{dimH} · {(numFrames/fps).toFixed(0)}s · {fps}fps</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Download */}
          {result && (
            <a href={`${api}${result}`} download
              className="flex items-center justify-center gap-2 w-full py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-white/70 hover:text-white text-sm font-semibold transition-all border border-white/[0.07]">
              <Download size={15} /> Download Video
            </a>
          )}

          {/* Active agent info card */}
          {activeAgent !== 'auto' && (() => {
            const ag = agents.find(a => a.id === activeAgent)
            if (!ag) return null
            return (
              <div className="card !p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{ag.emoji}</span>
                  <div>
                    <p className="text-sm font-bold text-white/80">{ag.name} Agent</p>
                    <p className="text-xs text-white/35">{ag.desc}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-400 border border-purple-500/20">
                    📷 {ag.camera?.replace('_',' ')}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-600/20 text-orange-400 border border-orange-500/20">
                    🎵 {ag.music}
                  </span>
                  {ag.effects?.map(fx => (
                    <span key={fx} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/35 border border-white/[0.05]">
                      {fx.replace('_',' ')}
                    </span>
                  ))}
                </div>
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}
