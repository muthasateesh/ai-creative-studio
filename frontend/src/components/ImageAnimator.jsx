import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Upload, Play, Download, RefreshCw, Film, X,
  Mic, Music2, Volume2, Settings2, ChevronDown, ChevronUp, Wand2, Sparkles
} from 'lucide-react'

const RESOLUTIONS = [
  { label: '720p (1280×720)',    w: 1280, h: 720  },
  { label: '1080p (1920×1080)', w: 1920, h: 1080 },
  { label: 'Square (1080×1080)',w: 1080, h: 1080 },
  { label: 'Portrait (720×1280)',w: 720, h: 1280  },
]

const STYLE_ICONS = {
  ken_burns:'🎬', zoom_in:'🔍', zoom_out:'🔭', breathe:'💨',
  float:'🕊️', pan_right:'➡️', pan_left:'⬅️', cinematic:'🎞️',
  glitch:'⚡', ripple:'🌊', bounce:'🏀', rotate:'🔄',
}
const MUSIC_ICONS = {
  none:'🔇', upbeat:'🎵', calm:'🌿', epic:'⚔️', cinematic:'🎬', jazz:'🎷', electronic:'🎛️',
}

const PIPELINE = ['rendering','generating voice','generating music','mixing audio']
const STATUS_LABEL = {
  queued:'Queued…', rendering:'Rendering frames…',
  'generating voice':'Generating voice…', 'generating music':'Composing music…',
  'mixing audio':'Mixing audio…', done:'Done!', error:'Error',
}

const PROMPT_EXAMPLES = [
  'A peaceful nature landscape with calm ambient music',
  'Cinematic dramatic reveal with epic background score',
  'Futuristic digital glitch effect with electronic music',
  'Warm portrait with gentle breathing animation',
  'Ocean waves with ripple effect and relaxing music',
  'Epic space scene zooming into the cosmos',
]

export default function ImageAnimator({ api }) {
  const [animStyles,  setAnimStyles]  = useState({})
  const [musicStyles, setMusicStyles] = useState({})
  const [voices,      setVoices]      = useState([])

  const [image,   setImage]   = useState(null)
  const [prompt,  setPrompt]  = useState('')
  const [dragging, setDragging] = useState(false)

  // suggestion state
  const [suggestion, setSuggestion] = useState(null)  // { anim_style, music_style, anim_label, music_label }
  const suggestTimer = useRef(null)

  // advanced panel
  const [showAdvanced, setShowAdvanced] = useState(false)

  // advanced controls
  const [manualStyle,  setManualStyle]  = useState('auto')
  const [duration,     setDuration]     = useState(6)
  const [fps,          setFps]          = useState(30)
  const [resolution,   setResolution]   = useState(RESOLUTIONS[0])
  const [manualMusic,  setManualMusic]  = useState('auto')
  const [musicVol,     setMusicVol]     = useState(30)

  // voice
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [narratePrompt, setNarratePrompt] = useState(false)
  const [voiceText,    setVoiceText]    = useState('')
  const [voiceName,    setVoiceName]    = useState('en-US-AriaNeural')
  const [voiceSearch,  setVoiceSearch]  = useState('')
  const [voiceRate,    setVoiceRate]    = useState(0)
  const [voicePitch,   setVoicePitch]   = useState(0)

  const [task,    setTask]    = useState(null)
  const fileRef   = useRef()
  const pollRef   = useRef()

  useEffect(() => {
    fetch(`${api}/api/animate/styles`).then(r => r.json()).then(setAnimStyles).catch(() => {})
    fetch(`${api}/api/animate/music-styles`).then(r => r.json()).then(setMusicStyles).catch(() => {})
    fetch(`${api}/api/voice/voices`).then(r => r.json()).then(d => setVoices(d.voices || [])).catch(() => {})
  }, [api])

  // debounced prompt → suggestion
  useEffect(() => {
    clearTimeout(suggestTimer.current)
    if (!prompt.trim()) { setSuggestion(null); return }
    suggestTimer.current = setTimeout(async () => {
      try {
        const form = new FormData()
        form.append('prompt', prompt)
        const res  = await fetch(`${api}/api/animate/suggest`, { method: 'POST', body: form })
        const data = await res.json()
        setSuggestion(data)
      } catch {}
    }, 400)
  }, [prompt, api])

  const pickFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return
    setImage({ file, preview: URL.createObjectURL(file) })
    setTask(null)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0])
  }, [])

  const pollTask = (id) => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const data = await fetch(`${api}/api/animate/task/${id}`).then(r => r.json())
        setTask(t => ({ ...t, ...data }))
        if (data.status === 'done' || data.status === 'error') clearInterval(pollRef.current)
      } catch {}
    }, 1000)
  }

  const generate = async () => {
    if (!image || !prompt.trim()) return
    const form = new FormData()
    form.append('file',           image.file)
    form.append('prompt',         prompt)
    form.append('style',          manualStyle)
    form.append('duration',       duration)
    form.append('fps',            fps)
    form.append('width',          resolution.w)
    form.append('height',         resolution.h)
    form.append('voice_text',     voiceEnabled && !narratePrompt ? voiceText : '')
    form.append('voice_name',     voiceName)
    form.append('voice_rate',     `${voiceRate >= 0 ? '+' : ''}${voiceRate}%`)
    form.append('voice_pitch',    `${voicePitch >= 0 ? '+' : ''}${voicePitch}Hz`)
    form.append('music_style',    manualMusic)
    form.append('music_vol',      (musicVol / 100).toFixed(2))
    form.append('narrate_prompt', voiceEnabled && narratePrompt ? 'true' : 'false')

    setTask({ status: 'queued', progress: 0 })
    try {
      const res  = await fetch(`${api}/api/animate/generate`, { method: 'POST', body: form })
      const data = await res.json()
      setTask(t => ({ ...t, id: data.task_id, resolved_style: data.resolved_style, resolved_music: data.resolved_music }))
      pollTask(data.task_id)
    } catch (e) {
      setTask({ status: 'error', error: e.message })
    }
  }

  const isRunning = task && PIPELINE.includes(task.status) || task?.status === 'queued'
  const canGenerate = image && prompt.trim() && !isRunning

  const filteredVoices = voices.filter(v =>
    v.ShortName?.toLowerCase().includes(voiceSearch.toLowerCase()) ||
    v.FriendlyName?.toLowerCase().includes(voiceSearch.toLowerCase())
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
          <Wand2 size={22} className="text-pink-400" /> Image Animator
        </h2>
        <p className="text-white/40 text-sm">Upload an image, describe it, and generate an animated video with music and voice</p>
      </div>

      {/* ── Step 1: Upload ── */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !image && fileRef.current?.click()}
        className={`relative rounded-2xl border-2 border-dashed transition-all duration-300 overflow-hidden cursor-pointer
          ${dragging ? 'border-purple-400 bg-purple-900/20 scale-[1.01]' : ''}
          ${image ? 'border-white/10 h-72' : 'border-white/20 hover:border-purple-500/50 hover:bg-white/[0.02] h-52 flex items-center justify-center'}`}
      >
        <input ref={fileRef} type="file" accept="image/*" className="hidden"
          onChange={e => pickFile(e.target.files[0])} />

        {image ? (
          <>
            <img src={image.preview} alt="uploaded"
              className="w-full h-full object-contain bg-black/50" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none" />
            <div className="absolute top-3 left-3 bg-green-500/20 border border-green-500/40 text-green-300 text-xs px-2.5 py-1 rounded-full flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" /> Image loaded
            </div>
            <button onClick={e => { e.stopPropagation(); setImage(null); setTask(null); setPrompt('') }}
              className="absolute top-3 right-3 p-1.5 rounded-lg bg-black/70 hover:bg-red-600/80 transition-colors">
              <X size={14} className="text-white" />
            </button>
            <button onClick={e => { e.stopPropagation(); fileRef.current?.click() }}
              className="absolute bottom-3 right-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-black/70 hover:bg-white/10 text-xs text-white/70 transition-colors">
              <Upload size={12} /> Change image
            </button>
          </>
        ) : (
          <div className="text-center px-6 select-none">
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-purple-600/20 to-pink-600/20 border border-white/10 flex items-center justify-center mx-auto mb-4">
              <Upload size={32} className="text-white/30" />
            </div>
            <p className="text-white/60 font-semibold text-lg">Drop your image here</p>
            <p className="text-white/30 text-sm mt-1">or click to browse &nbsp;·&nbsp; PNG · JPG · WEBP</p>
          </div>
        )}
      </div>

      {/* ── Step 2: Prompt (appears after upload) ── */}
      {image && (
        <div className="space-y-3 animate-fade-in">
          <label className="block text-sm font-semibold text-white/70">
            Describe your video&nbsp;
            <span className="text-white/30 font-normal">(AI will choose animation &amp; music automatically)</span>
          </label>

          {/* Prompt input */}
          <div className="relative">
            <Sparkles size={16} className="absolute left-4 top-3.5 text-purple-400 pointer-events-none" />
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="e.g. A peaceful sunset landscape with calming music and gentle voice narration…"
              rows={3}
              className="input-field w-full pl-10 pr-4 resize-none text-sm leading-relaxed"
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generate() }}
            />
            <div className="absolute bottom-2 right-3 text-xs text-white/20">Ctrl+Enter to generate</div>
          </div>

          {/* Example prompts */}
          {!prompt && (
            <div className="flex flex-wrap gap-2">
              {PROMPT_EXAMPLES.map(ex => (
                <button key={ex} onClick={() => setPrompt(ex)}
                  className="text-xs px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-white/40 hover:text-white/70 hover:bg-white/[0.08] transition-all">
                  {ex}
                </button>
              ))}
            </div>
          )}

          {/* AI suggestion badge */}
          {suggestion && prompt && (
            <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-purple-900/20 border border-purple-500/30">
              <Sparkles size={14} className="text-purple-400 shrink-0" />
              <span className="text-xs text-white/60">AI selected:</span>
              <span className="text-xs font-semibold text-purple-300">
                {STYLE_ICONS[suggestion.anim_style]} {suggestion.anim_label}
              </span>
              <span className="text-white/20 text-xs">+</span>
              <span className="text-xs font-semibold text-orange-300">
                {MUSIC_ICONS[suggestion.music_style]} {suggestion.music_label} music
              </span>
              {manualStyle === 'auto' && manualMusic === 'auto' && (
                <span className="ml-auto text-xs text-white/25 italic">auto</span>
              )}
            </div>
          )}

          {/* Voice narration toggle */}
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <Mic size={15} className="text-green-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-white/70 font-medium">Add voice narration</p>
              <p className="text-xs text-white/30">Speak the prompt text as voice over</p>
            </div>
            <div className="flex items-center gap-2">
              {voiceEnabled && (
                <button onClick={() => setNarratePrompt(v => !v)}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-all
                    ${narratePrompt ? 'bg-green-600/30 border-green-500/50 text-green-300' : 'bg-white/[0.04] border-white/10 text-white/30'}`}>
                  {narratePrompt ? 'Using prompt' : 'Custom text'}
                </button>
              )}
              <button onClick={() => setVoiceEnabled(v => !v)}
                className={`relative w-10 h-5 rounded-full transition-colors ${voiceEnabled ? 'bg-green-500' : 'bg-white/10'}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${voiceEnabled ? 'left-5' : 'left-0.5'}`} />
              </button>
            </div>
          </div>

          {/* Custom voice text (only if narrate_prompt is off) */}
          {voiceEnabled && !narratePrompt && (
            <textarea
              value={voiceText}
              onChange={e => setVoiceText(e.target.value)}
              placeholder="Type your narration text here…"
              rows={2}
              className="input-field w-full resize-none text-sm"
            />
          )}

          {/* ── Generate button ── */}
          <button onClick={generate} disabled={!canGenerate}
            className="w-full py-4 rounded-2xl font-bold text-white text-base transition-all duration-200
              bg-gradient-to-r from-purple-600 via-pink-600 to-blue-600
              hover:from-purple-500 hover:via-pink-500 hover:to-blue-500
              hover:scale-[1.01] hover:shadow-lg hover:shadow-purple-500/20
              disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100
              flex items-center justify-center gap-3">
            {isRunning ? (
              <>
                <RefreshCw size={18} className="animate-spin" />
                <span>{STATUS_LABEL[task?.status] || 'Processing…'}
                  {task?.progress > 0 ? ` ${task.progress}%` : ''}</span>
              </>
            ) : (
              <>
                <Play size={18} />
                <span>Generate Video</span>
                {prompt && <span className="text-white/50 text-sm font-normal">Ctrl+Enter</span>}
              </>
            )}
          </button>

          {/* Progress bar */}
          {isRunning && (
            <div className="space-y-2">
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-purple-500 via-pink-500 to-blue-500 transition-all duration-700 rounded-full"
                  style={{ width: `${Math.max(task?.progress || 0, 3)}%` }} />
              </div>
              <div className="flex gap-2 justify-center">
                {PIPELINE.map((s, i) => {
                  const idx   = PIPELINE.indexOf(task?.status)
                  const done  = idx > i
                  const active= task?.status === s
                  return (
                    <span key={s}
                      className={`px-2.5 py-0.5 rounded-full text-xs font-medium border transition-all
                        ${active  ? 'bg-purple-600/40 border-purple-400/60 text-purple-200 animate-pulse'
                        : done   ? 'bg-white/5 border-white/10 text-white/25 line-through'
                        : 'bg-white/[0.02] border-white/[0.05] text-white/20'}`}>
                      {s}
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          {/* Resolved tags (after generation starts) */}
          {task?.resolved_style && (
            <div className="flex gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-purple-600/20 border border-purple-500/30 text-purple-300">
                {STYLE_ICONS[task.resolved_style]} {STYLES_MAP[task.resolved_style] || task.resolved_style}
              </span>
              <span className="px-2.5 py-1 rounded-full bg-orange-600/20 border border-orange-500/30 text-orange-300">
                {MUSIC_ICONS[task.resolved_music]} {task.resolved_music} music
              </span>
            </div>
          )}

          {/* Result video */}
          {task?.status === 'done' && task.url && (
            <div className="rounded-2xl overflow-hidden bg-black border border-white/10 shadow-xl">
              <video src={`${api}${task.url}`} controls autoPlay loop
                className="w-full max-h-[400px] object-contain" />
              <div className="flex items-center justify-between px-4 py-3 bg-white/[0.03]">
                <span className="text-sm text-white/50 flex items-center gap-2">
                  <Film size={14} className="text-purple-400" /> Video ready
                </span>
                <div className="flex gap-2">
                  <button onClick={() => { setTask(null); setPrompt('') }}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 text-xs transition-colors">
                    New video
                  </button>
                  <a href={`${api}${task.url}`} download
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium transition-all">
                    <Download size={13} /> Download
                  </a>
                </div>
              </div>
            </div>
          )}

          {task?.status === 'error' && (
            <div className="rounded-xl bg-red-900/20 border border-red-500/30 px-4 py-3 text-red-400 text-sm">
              {task.error}
            </div>
          )}

          {/* ── Advanced settings ── */}
          <button onClick={() => setShowAdvanced(v => !v)}
            className="flex items-center gap-2 text-xs text-white/30 hover:text-white/60 transition-colors mx-auto">
            <Settings2 size={13} />
            Advanced settings
            {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          {showAdvanced && (
            <div className="space-y-4 pt-2 border-t border-white/[0.06]">
              {/* Manual style override */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
                  Override Animation Style &nbsp;<span className="text-white/20 normal-case font-normal">(leave auto to use AI)</span>
                </label>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                  <button onClick={() => setManualStyle('auto')}
                    className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all
                      ${manualStyle === 'auto' ? 'bg-purple-600/30 border-purple-500/60 text-purple-200' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                    ✨ Auto
                  </button>
                  {Object.entries(animStyles).map(([id, label]) => (
                    <button key={id} onClick={() => setManualStyle(id)}
                      className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all
                        ${manualStyle === id ? 'bg-purple-600/30 border-purple-500/60 text-white' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                      {STYLE_ICONS[id]} {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Manual music override */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
                  Override Music &nbsp;<span className="text-white/20 normal-case font-normal">(leave auto to use AI)</span>
                </label>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                  <button onClick={() => setManualMusic('auto')}
                    className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all
                      ${manualMusic === 'auto' ? 'bg-orange-600/30 border-orange-500/60 text-orange-200' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                    ✨ Auto
                  </button>
                  {Object.entries(musicStyles).map(([id, label]) => (
                    <button key={id} onClick={() => setManualMusic(id)}
                      className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all
                        ${manualMusic === id ? 'bg-orange-600/30 border-orange-500/60 text-white' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                      {MUSIC_ICONS[id]} {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Music volume */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-white/40 flex items-center gap-1"><Volume2 size={11} /> Music volume</span>
                    <span className="text-white/60">{musicVol}%</span>
                  </div>
                  <input type="range" min={5} max={80} value={musicVol}
                    onChange={e => setMusicVol(Number(e.target.value))}
                    className="w-full accent-orange-500" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-white/40">Duration</span>
                    <span className="text-white/60">{duration}s</span>
                  </div>
                  <input type="range" min={2} max={20} value={duration}
                    onChange={e => setDuration(Number(e.target.value))}
                    className="w-full accent-purple-500" />
                </div>
              </div>

              {/* FPS + Resolution */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs text-white/40">Frame Rate</label>
                  <div className="flex gap-1.5">
                    {[24, 30, 60].map(f => (
                      <button key={f} onClick={() => setFps(f)}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all
                          ${fps === f ? 'bg-blue-600/40 border-blue-500/60 text-blue-300' : 'bg-white/[0.03] border-white/[0.06] text-white/40 hover:text-white/70'}`}>
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-white/40">Resolution</label>
                  <select value={resolution.label} onChange={e => setResolution(RESOLUTIONS.find(r => r.label === e.target.value))}
                    className="input-field w-full text-xs py-1.5">
                    {RESOLUTIONS.map(r => <option key={r.label} value={r.label}>{r.label}</option>)}
                  </select>
                </div>
              </div>

              {/* Voice controls */}
              {voiceEnabled && (
                <div className="space-y-2 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  <label className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
                    <Mic size={12} /> Voice settings
                  </label>
                  <input value={voiceSearch} onChange={e => setVoiceSearch(e.target.value)}
                    placeholder="Search voice…" className="input-field w-full text-xs py-1.5" />
                  <div className="max-h-28 overflow-y-auto space-y-0.5 rounded-lg bg-black/20 p-1">
                    {filteredVoices.slice(0, 80).map(v => (
                      <button key={v.ShortName} onClick={() => setVoiceName(v.ShortName)}
                        className={`w-full text-left px-2 py-1 rounded text-xs transition-colors
                          ${voiceName === v.ShortName ? 'bg-green-600/30 text-green-300' : 'text-white/50 hover:text-white/80 hover:bg-white/5'}`}>
                        {v.FriendlyName || v.ShortName}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-white/40">Speed</span>
                        <span className="text-white/60">{voiceRate > 0 ? '+' : ''}{voiceRate}%</span>
                      </div>
                      <input type="range" min={-50} max={50} value={voiceRate}
                        onChange={e => setVoiceRate(Number(e.target.value))} className="w-full accent-green-500" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-white/40">Pitch</span>
                        <span className="text-white/60">{voicePitch > 0 ? '+' : ''}{voicePitch}Hz</span>
                      </div>
                      <input type="range" min={-10} max={10} value={voicePitch}
                        onChange={e => setVoicePitch(Number(e.target.value))} className="w-full accent-green-500" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// needed for resolved style tag rendering
const STYLES_MAP = {
  ken_burns:'Ken Burns', zoom_in:'Zoom In', zoom_out:'Zoom Out', breathe:'Breathe',
  float:'Float', pan_right:'Pan Right', pan_left:'Pan Left', cinematic:'Cinematic',
  glitch:'Glitch', ripple:'Ripple Wave', bounce:'Bounce', rotate:'Slow Rotate',
}
