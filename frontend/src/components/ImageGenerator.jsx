import { useState } from 'react'
import { Image, Download, RefreshCw, Wand2, Settings2 } from 'lucide-react'
import axios from 'axios'

const STYLES = [
  { id: 'realistic', label: 'Photorealistic' },
  { id: 'anime', label: 'Anime' },
  { id: 'oil_painting', label: 'Oil Painting' },
  { id: 'watercolor', label: 'Watercolor' },
  { id: 'sketch', label: 'Sketch' },
  { id: '3d', label: '3D Render' },
]

const SIZES = [
  { label: '1:1', w: 1024, h: 1024 },
  { label: '16:9', w: 1280, h: 720 },
  { label: '9:16', w: 720, h: 1280 },
  { label: '4:3', w: 1024, h: 768 },
]

const EXAMPLE_PROMPTS = [
  'A majestic dragon flying over a fantasy city at sunset',
  'Portrait of a cyberpunk woman with neon lights in the rain',
  'Enchanted forest with glowing mushrooms and fairies',
  'Futuristic spaceship interior with holographic displays',
  'Mountain landscape with northern lights and a cozy cabin',
]

export default function ImageGenerator({ api }) {
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('blurry, bad quality, distorted')
  const [style, setStyle] = useState('realistic')
  const [size, setSize] = useState(SIZES[0])
  const [steps, setSteps] = useState(25)
  const [guidance, setGuidance] = useState(7.5)
  const [numImages, setNumImages] = useState(1)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const pollTask = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${api}/api/images/task/${taskId}`)
        const data = res.data
        setProgress(data.progress || 0)
        setStatus(data.status)

        if (data.status === 'completed') {
          clearInterval(interval)
          setResults(data.results || [])
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
    }, 1500)
  }

  const generate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError('')
    setResults([])
    setProgress(0)
    setStatus('queued')

    try {
      const res = await axios.post(`${api}/api/images/generate`, {
        prompt,
        negative_prompt: negativePrompt,
        style,
        width: size.w,
        height: size.h,
        steps,
        guidance_scale: guidance,
        num_images: numImages,
      })
      pollTask(res.data.task_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start generation')
      setLoading(false)
    }
  }

  const downloadImage = (url) => {
    const a = document.createElement('a')
    a.href = `${api}${url}`
    a.download = url.split('/').pop()
    a.click()
  }

  const statusLabel = {
    queued: 'Queued...',
    loading_model: 'Loading AI model (first time takes ~2 min)...',
    generating: 'Generating your image...',
    completed: 'Done!',
    failed: 'Failed',
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold gradient-text mb-2">AI Image Generator</h2>
        <p className="text-white/50">Transform your words into stunning visuals with Stable Diffusion XL</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Controls */}
        <div className="space-y-5">
          {/* Prompt */}
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-2">Describe your image</label>
            <textarea
              className="input-field resize-none h-28"
              placeholder="A majestic lion in a golden savanna at sunset, ultra detailed..."
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
            />
            {/* Example prompts */}
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPrompt(p)}
                  className="text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80 transition-all truncate max-w-[140px]"
                  title={p}
                >
                  {p.slice(0, 30)}...
                </button>
              ))}
            </div>
          </div>

          {/* Style */}
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-3">Style</label>
            <div className="grid grid-cols-3 gap-2">
              {STYLES.map(s => (
                <button
                  key={s.id}
                  onClick={() => setStyle(s.id)}
                  className={`py-2 px-3 rounded-xl text-sm font-medium transition-all ${
                    style === s.id
                      ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                      : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size */}
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-3">Aspect Ratio</label>
            <div className="grid grid-cols-4 gap-2">
              {SIZES.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setSize(s)}
                  className={`py-2 px-3 rounded-xl text-sm font-medium transition-all ${
                    size.label === s.label
                      ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                      : 'bg-white/5 text-white/50 hover:bg-white/10'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Number of images */}
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-white/70">Number of Images</label>
              <span className="text-purple-400 font-bold">{numImages}</span>
            </div>
            <input type="range" min={1} max={4} value={numImages} onChange={e => setNumImages(+e.target.value)}
              className="w-full accent-purple-500" />
          </div>

          {/* Advanced */}
          <div className="card">
            <button onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-white/50 hover:text-white/80 transition-colors">
              <Settings2 size={16} />
              Advanced Settings {showAdvanced ? '▲' : '▼'}
            </button>
            {showAdvanced && (
              <div className="mt-4 space-y-4 animate-slide-up">
                <div>
                  <label className="block text-xs text-white/50 mb-1">Negative Prompt</label>
                  <input type="text" className="input-field text-sm" value={negativePrompt}
                    onChange={e => setNegativePrompt(e.target.value)} />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-white/50 mb-1">
                    <span>Steps: {steps}</span>
                    <span>More steps = better quality</span>
                  </div>
                  <input type="range" min={10} max={50} value={steps} onChange={e => setSteps(+e.target.value)}
                    className="w-full accent-purple-500" />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-white/50 mb-1">
                    <span>Guidance Scale: {guidance}</span>
                    <span>How closely to follow prompt</span>
                  </div>
                  <input type="range" min={1} max={20} step={0.5} value={guidance}
                    onChange={e => setGuidance(+e.target.value)} className="w-full accent-purple-500" />
                </div>
              </div>
            )}
          </div>

          <button onClick={generate} disabled={loading || !prompt.trim()}
            className="btn-primary w-full flex items-center justify-center gap-2">
            {loading ? (
              <><RefreshCw size={18} className="animate-spin" /> Generating...</>
            ) : (
              <><Wand2 size={18} /> Generate Image</>
            )}
          </button>

          {/* Progress */}
          {loading && (
            <div className="card animate-fade-in">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-white/60">{statusLabel[status] || status}</span>
                <span className="text-purple-400">{progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              {status === 'loading_model' && (
                <p className="text-xs text-yellow-400/70 mt-2">
                  ⚡ AI model downloads ~7GB on first use. Subsequent generations are instant.
                </p>
              )}
            </div>
          )}

          {error && (
            <div className="card border-red-500/20 bg-red-500/5">
              <p className="text-red-400 text-sm">❌ {error}</p>
            </div>
          )}
        </div>

        {/* Results */}
        <div>
          {results.length > 0 ? (
            <div className="space-y-4 animate-fade-in">
              <h3 className="text-lg font-semibold text-white">Generated Images</h3>
              <div className={`grid gap-3 ${results.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                {results.map((url, i) => (
                  <div key={i} className="relative group rounded-2xl overflow-hidden border border-white/10">
                    <img src={`${api}${url}`} alt={`Generated ${i + 1}`}
                      className="w-full object-cover" />
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                      <button onClick={() => downloadImage(url)}
                        className="flex items-center gap-2 bg-white/20 hover:bg-white/30 backdrop-blur px-4 py-2 rounded-xl text-white text-sm font-medium transition-all">
                        <Download size={16} /> Download
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-80 card">
              <Image size={48} className="text-white/10 mb-4" />
              <p className="text-white/30 text-center">Your generated images will appear here</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
