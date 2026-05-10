import { useState } from 'react'
import { Video, Download, RefreshCw, Wand2 } from 'lucide-react'
import axios from 'axios'

const EXAMPLE_PROMPTS = [
  'A rocket launching into space with fire and smoke',
  'Ocean waves crashing on a rocky shore at sunset',
  'A dancer performing ballet on a stage with spotlights',
  'Snow falling gently in a winter forest',
  'A sports car drifting around a corner on a racing track',
]

export default function VideoGenerator({ api }) {
  const [prompt, setPrompt] = useState('')
  const [numFrames, setNumFrames] = useState(24)
  const [fps, setFps] = useState(8)
  const [steps, setSteps] = useState(25)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const pollTask = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${api}/api/videos/task/${taskId}`)
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
      const res = await axios.post(`${api}/api/videos/generate`, {
        prompt,
        num_frames: numFrames,
        fps,
        steps,
        width: 576,
        height: 320,
      })
      pollTask(res.data.task_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start generation')
      setLoading(false)
    }
  }

  const statusLabel = {
    queued: 'Queued...',
    loading_model: 'Loading video AI model (first time ~3 min)...',
    generating: 'Generating your video...',
    completed: 'Done!',
    failed: 'Failed',
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold gradient-text mb-2">AI Video Generator</h2>
        <p className="text-white/50">Generate short AI videos from text using Zeroscope V2</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-5">
          <div className="card">
            <label className="block text-sm font-medium text-white/70 mb-2">Describe your video</label>
            <textarea
              className="input-field resize-none h-28"
              placeholder="Ocean waves crashing on a rocky shore at golden hour..."
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button key={i} onClick={() => setPrompt(p)}
                  className="text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80 transition-all truncate max-w-[160px]"
                  title={p}>
                  {p.slice(0, 30)}...
                </button>
              ))}
            </div>
          </div>

          <div className="card space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-white/70">Number of Frames</span>
                <span className="text-blue-400 font-bold">{numFrames}</span>
              </div>
              <input type="range" min={8} max={48} step={4} value={numFrames}
                onChange={e => setNumFrames(+e.target.value)} className="w-full accent-blue-500" />
              <p className="text-xs text-white/30 mt-1">
                Duration: ~{(numFrames / fps).toFixed(1)}s at {fps} FPS
              </p>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-white/70">FPS</span>
                <span className="text-blue-400 font-bold">{fps}</span>
              </div>
              <input type="range" min={4} max={24} step={2} value={fps}
                onChange={e => setFps(+e.target.value)} className="w-full accent-blue-500" />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-white/70">Quality Steps</span>
                <span className="text-blue-400 font-bold">{steps}</span>
              </div>
              <input type="range" min={10} max={50} value={steps}
                onChange={e => setSteps(+e.target.value)} className="w-full accent-blue-500" />
            </div>
          </div>

          <div className="card bg-blue-950/20 border-blue-500/20">
            <p className="text-xs text-blue-300/70">
              💡 <strong>Tips:</strong> Video generation takes 3-10 minutes per video.
              First generation also downloads the model (~2.5GB). Keep descriptions motion-focused for best results.
            </p>
          </div>

          <button onClick={generate} disabled={loading || !prompt.trim()}
            className="w-full py-3 px-6 rounded-xl font-semibold text-white bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
            {loading ? (
              <><RefreshCw size={18} className="animate-spin" /> Generating...</>
            ) : (
              <><Wand2 size={18} /> Generate Video</>
            )}
          </button>

          {loading && (
            <div className="card animate-fade-in">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-white/60">{statusLabel[status] || status}</span>
                <span className="text-blue-400">{progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="h-full rounded-full transition-all duration-300 bg-gradient-to-r from-blue-500 to-cyan-500"
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
              <h3 className="text-lg font-semibold text-white">Generated Video</h3>
              <div className="rounded-2xl overflow-hidden border border-white/10 bg-black">
                <video src={`${api}${result}`} controls autoPlay loop className="w-full" />
              </div>
              <a href={`${api}${result}`} download
                className="flex items-center justify-center gap-2 py-3 px-6 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-all">
                <Download size={18} /> Download Video
              </a>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-80 card">
              <Video size={48} className="text-white/10 mb-4" />
              <p className="text-white/30 text-center">Your generated video will appear here</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
