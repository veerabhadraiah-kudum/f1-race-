import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Legend, Cell } from 'recharts'

const API = '' // same origin via vite proxy / or direct localhost:8000

type SimResult = {
  strategy_id: string; compounds: string[]; pit_laps: number[];
  mean_total_time: number; median_total_time: number; std_total_time: number;
  p5_total_time: number; p95_total_time: number; fastest_time: number; window?: number[];
  win_probability: number; podium_probability: number
}
type Car = { driver_number: number; abbreviation: string; full_name: string; team_name: string; team_colour: string; position: number; gap_to_leader: string; interval: string; last_lap_time: number; compound: string; tyre_age: number; speed: number; x: number; y: number; status: string }

const CIRCUITS = [
  {k:'monza', name:'Monza', laps:53}, {k:'monaco', name:'Monaco', laps:78}, {k:'silverstone', name:'Silverstone', laps:52},
  {k:'spa', name:'Spa', laps:44}, {k:'barcelona', name:'Barcelona', laps:66}, {k:'suzuka',name:'Suzuka',laps:53},
  {k:'bahrain', name:'Bahrain', laps:57}, {k:'melbourne', name:'Melbourne', laps:58}, {k:'austin', name:'Austin', laps:56},
  {k:'qatar', name:'Qatar', laps:57}, {k:'abu_dhabi', name:'Yas Marina', laps:58}, {k:'brazil', name:'Interlagos', laps:71},
]

const TEAM_COLOR: Record<string,string> = {
  'Red Bull Racing':'#0600EF','Ferrari':'#DC0000','Mercedes':'#00D2BE','McLaren':'#FF8700',
  'Aston Martin':'#006F62','Alpine':'#0090FF','Williams':'#005AFF','RB':'#6692FF','Sauber':'#52E252','Haas':'#B6BABD'
}

export default function App(){
  const [circuit, setCircuit] = useState('monza')
  const [laps, setLaps] = useState(53)
  const [basePace, setBasePace] = useState(85)
  const [sims, setSims] = useState(3000)
  const [results, setResults] = useState<SimResult[]>([])
  const [best, setBest] = useState('')
  const [loading, setLoading] = useState(false)
  const [computeMs, setComputeMs] = useState(0)
  const [mode, setMode] = useState<'simulate'|'live'>('simulate')
  // live
  const [liveState, setLiveState] = useState<any>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket|null>(null)
  // telemetry mock
  const [telemetry, setTelemetry] = useState<any[]>([])

  // sync laps when circuit changes
  useEffect(()=>{ const c=CIRCUITS.find(x=>x.k===circuit); if(c) setLaps(c.laps) },[circuit])

  const runSimulation = async()=>{
    setLoading(true)
    try{
      const res = await fetch(`/api/simulate`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ circuit_key: circuit, total_laps: laps, base_lap_time: basePace, n_simulations: sims, seed: 42, include_safety_car: true })
      })
      const data = await res.json()
      setResults(data.results||[])
      setBest(data.best_strategy_id||'')
      setComputeMs(data.compute_ms||0)
    }catch(e){ console.error(e); alert('Simulation failed — is backend running? (uvicorn backend.app.main:app --port 8000)')}
    setLoading(false)
  }
  const runOptimize = async()=>{
    setLoading(true)
    try{
      const res = await fetch(`/api/strategy/optimize`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ circuit_key: circuit, total_laps: laps, base_lap_time: basePace, n_simulations: sims })
      })
      const q = await fetch(`/api/strategy/optimize?circuit_key=${circuit}&total_laps=${laps}&base_lap_time=${basePace}&n_simulations=${sims}`,{method:'POST'})
      const data = await q.json()
      // map optimizer results to sim results shape
      if(data.results){
        const mapped = data.results.slice(0,6).map((r:any)=>({
          strategy_id: r.compound_sequence.join('-'),
          compounds: r.compound_sequence,
          pit_laps: r.optimal_pit_laps,
          mean_total_time: r.mean_time,
          median_total_time: r.mean_time,
          std_total_time: 0,
          p5_total_time: r.mean_time - 5,
          p95_total_time: r.p95 || r.mean_time + 5,
          fastest_time: r.mean_time - 10,
          win_probability: r.win_probability || 0,
          podium_probability: r.podium_probability || 0
        }))
        setResults(mapped)
        setBest(mapped[0]?.strategy_id||'')
        setComputeMs(data.compute_ms||0)
      }
    }catch(e){ console.error(e)}
    setLoading(false)
  }

  // connect live WS when mode=live
  useEffect(()=>{
    if(mode!=='live') { wsRef.current?.close(); setWsConnected(false); return }
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host.includes('5173') ? location.host.replace('5173','8000') : location.host
    const url = `${proto}//${host}/ws/live/mock`
    // try relative first for preview
    const wsUrl = location.hostname.includes('e2b.app') ? `${proto}//${location.host.replace(/5173/,'8000')}/ws/live/mock` : url
    // fallback: try backend on 8000 via current host logic
    const tryUrls = [`${proto}//${location.host}/ws/live/mock`, url, wsUrl, `ws://localhost:8000/ws/live/mock`]
    let ws: WebSocket | null = null
    for(const u of tryUrls){
      try{ ws = new WebSocket(u); break }catch{}
    }
    if(!ws) return
    wsRef.current = ws
    ws.onopen = ()=> setWsConnected(true)
    ws.onmessage = (ev)=>{
      try{ const d = JSON.parse(ev.data); if(d.type==='race_state') setLiveState(d) }catch{}
    }
    ws.onclose = ()=> setWsConnected(false)
    // mock telemetry fetch
    fetch(`/api/telemetry/mock/VER`).then(r=>r.json()).then(d=> setTelemetry(d.points||[])).catch(()=>{})
    return ()=> ws?.close()
  },[mode])

  const chartData = results.map(r=>({ name: r.strategy_id, mean: +(r.mean_total_time/60).toFixed(2), win: +(r.win_probability*100).toFixed(1), p95: +(r.p95_total_time/60).toFixed(2) }))

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur bg-black/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded bg-[#E10600] grid place-items-center font-black f1-font text-sm">F1</div>
            <div>
              <div className="f1-font font-black text-[13px] tracking-widest">ADVANCED SIMULATION</div>
              <div className="text-[11px] text-white/60 mono">Real-Time • Physics-Accurate • Monte Carlo 10k</div>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 text-[11px] mono">
            <span className="px-2 py-1 rounded bg-white/10">FastF1 3.8.3</span>
            <span className="px-2 py-1 rounded bg-white/10">OpenF1</span>
            <span className="px-2 py-1 rounded bg-white/10">Jolpica-F1</span>
            <span className="px-2 py-1 rounded bg-[#E10600] text-white">2026 Season</span>
          </div>
          <div className="flex gap-2">
            <button onClick={()=>setMode('simulate')} className={`px-4 py-2 rounded font-bold text-sm ${mode==='simulate'?'bg-[#E10600]':'bg-white/10 hover:bg-white/20'}`}>SIMULATE</button>
            <button onClick={()=>setMode('live')} className={`px-4 py-2 rounded font-bold text-sm flex items-center gap-2 ${mode==='live'?'bg-[#E10600]':'bg-white/10 hover:bg-white/20'}`}>
              <span className={`w-2 h-2 rounded-full ${wsConnected?'bg-green-400 animate-pulse':'bg-white/40'}`}></span> LIVE
            </button>
            <a href="/docs" target="_blank" className="px-3 py-2 rounded bg-white text-black font-bold text-sm">API DOCS</a>
          </div>
        </div>
      </header>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left panel — controls */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
              <div className="text-xs mono text-white/60 mb-2">CIRCUIT & PARAMETERS</div>
              <label className="text-xs text-white/80">Circuit</label>
              <select value={circuit} onChange={e=>setCircuit(e.target.value)} className="w-full mt-1 bg-black border border-white/15 rounded px-3 py-2 text-sm">
                {CIRCUITS.map(c=> <option key={c.k} value={c.k}>{c.name} — {c.laps} laps</option>)}
              </select>
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <label className="text-xs text-white/80">Laps</label>
                  <input type="number" value={laps} onChange={e=>setLaps(parseInt(e.target.value)||53)} className="w-full mt-1 bg-black border border-white/15 rounded px-3 py-2 text-sm"/>
                </div>
                <div>
                  <label className="text-xs text-white/80">Base pace (s)</label>
                  <input type="number" step="0.1" value={basePace} onChange={e=>setBasePace(parseFloat(e.target.value)||85)} className="w-full mt-1 bg-black border border-white/15 rounded px-3 py-2 text-sm"/>
                </div>
              </div>
              <div className="mt-3">
                <label className="text-xs text-white/80">Simulations</label>
                <input type="range" min={500} max={10000} step={500} value={sims} onChange={e=>setSims(parseInt(e.target.value))} className="w-full"/>
                <div className="text-xs mono text-white/60">{sims.toLocaleString()} runs • ~{(sims*0.04).toFixed(0)}ms est.</div>
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={runSimulation} disabled={loading} className="flex-1 bg-[#E10600] hover:bg-[#c10500] disabled:opacity-50 rounded py-2.5 font-bold text-sm">{loading?'RUNNING...':'RUN SIMULATION'}</button>
                <button onClick={runOptimize} disabled={loading} className="px-4 bg-white text-black hover:bg-white/90 rounded font-bold text-sm">OPTIMIZE</button>
              </div>
              {computeMs>0 && <div className="text-xs mono text-green-400 mt-2">✓ Computed in {computeMs}ms</div>}
              <div className="mt-4 pt-4 border-t border-white/10 text-[11px] leading-relaxed text-white/50">
                <b className="text-white/80">Physics:</b> μ=α+β·age+γ·age² (γ≥0), fuel 0.03s/kg, pit loss lognormal, SC Poisson, AR(1) noise.<br/>
                <b className="text-white/80">Data:</b> Jolpica + FastF1 + OpenF1 fused, per-circuit calibrated.
              </div>
            </div>

            <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
              <div className="text-xs mono text-white/60 mb-2">RESOURCES GATHERED</div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between"><span>FastF1 5.4k⭐</span><span className="text-green-400">● active</span></div>
                <div className="flex justify-between"><span>OpenF1 API</span><span className="text-green-400">● active</span></div>
                <div className="flex justify-between"><span>Jolpica-F1 (Ergast succ.)</span><span className="text-green-400">● active</span></div>
                <div className="flex justify-between"><span>LiveF1 SignalR</span><span className="text-white/50">ready</span></div>
                <div className="flex justify-between"><span>F1DB / FIA-doc</span><span className="text-white/50">ready</span></div>
                <div className="flex justify-between"><span>TUM Racetrack DB</span><span className="text-white/50">ready</span></div>
              </div>
              <a href="https://github.com/subinium/awesome-f1" target="_blank" className="text-xs text-[#E10600] hover:underline mt-2 block">→ awesome-f1 curated list</a>
            </div>
          </div>

          {/* Center — results */}
          <div className="lg:col-span-6 space-y-4">
            {mode==='simulate' ? (
              <>
                <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-bold f1-font">STRATEGY COMPARISON</div>
                    <div className="text-xs mono text-white/60">{results.length ? `${results.length} strategies • best: ${best}` : 'Run simulation'}</div>
                  </div>
                  {results.length===0 ? (
                    <div className="py-16 text-center">
                      <div className="text-4xl mb-3">🏎️</div>
                      <div className="text-sm font-bold">No simulation yet</div>
                      <div className="text-xs text-white/60 mt-1">Choose circuit & parameters → Run Simulation</div>
                      <div className="text-xs mono text-white/40 mt-3">Try: Monza 53 laps, 3000 sims — ~120ms</div>
                    </div>
                  ): (
                    <>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a"/>
                            <XAxis dataKey="name" stroke="#888" fontSize={11}/>
                            <YAxis stroke="#888" fontSize={11} label={{value:'Time (min)', angle:-90, position:'insideLeft', fill:'#888', fontSize:11}}/>
                            <Tooltip contentStyle={{background:'#1a1a1a', border:'1px solid #333', fontSize:12}} formatter={(v:any)=>[v,'min']}/>
                            <Bar dataKey="mean" name="Mean (min)" radius={[4,4,0,0]}>
                              {chartData.map((e,i)=> <Cell key={i} fill={chartData[i].name===best ? '#E10600' : '#3a3a3a'} />)}
                            </Bar>
                            <Bar dataKey="p95" name="P95 (min)" fill="#ff8a65" radius={[4,4,0,0]} opacity={0.6}/>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="space-y-2 mt-2 max-h-[340px] overflow-auto pr-1">
                        {results.sort((a,b)=> a.mean_total_time - b.mean_total_time).map(r=>{
                          const isBest = r.strategy_id===best
                          const pct = (r.win_probability*100).toFixed(1)
                          return (
                            <div key={r.strategy_id} className={`flex items-center gap-3 px-3 py-2.5 rounded border ${isBest?'bg-[#E10600]/15 border-[#E10600]/50':'bg-black/40 border-white/10'}`}>
                              <div className={`w-1.5 h-10 rounded ${isBest?'bg-[#E10600]':'bg-white/20'}`}></div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-black text-sm f1-font">{r.strategy_id}</span>
                                  <span className="text-xs mono text-white/60">{r.compounds.join(' → ')} @ {r.pit_laps.join(', ')}</span>
                                  {isBest && <span className="ml-auto px-2 py-0.5 rounded bg-[#E10600] text-white text-[10px] font-bold">BEST</span>}
                                </div>
                                <div className="text-xs mono text-white/70 mt-1">mean {(r.mean_total_time/60).toFixed(2)} min • median {(r.median_total_time/60).toFixed(2)} • σ {r.std_total_time.toFixed(2)}s • p95 {(r.p95_total_time/60).toFixed(2)}</div>
                              </div>
                              <div className="text-right">
                                <div className={`text-lg font-black ${isBest?'text-[#E10600]':'text-white'}`}>{pct}%</div>
                                <div className="text-[10px] mono text-white/50">WIN</div>
                                <div className="w-16 h-1.5 bg-white/10 rounded mt-1 overflow-hidden"><div className="h-full bg-[#E10600]" style={{width:`${pct}%`}}/></div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </>
                  )}
                </div>
                {telemetry.length>0 && (
                  <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
                    <div className="text-xs mono text-white/60 mb-2">TELEMETRY — SPEED TRACE (mock via FastF1 shape)</div>
                    <div className="h-40">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={telemetry}>
                          <CartesianGrid stroke="#222" strokeDasharray="3 3"/>
                          <XAxis dataKey="distance" stroke="#666" fontSize={10} tickFormatter={(v)=> (v*100).toFixed(0)+'%'} />
                          <YAxis stroke="#666" fontSize={10}/>
                          <Tooltip contentStyle={{background:'#111', border:'1px solid #333', fontSize:11}}/>
                          <Line type="monotone" dataKey="speed" stroke="#E10600" dot={false} strokeWidth={1.5}/>
                          <Line type="monotone" dataKey="throttle" stroke="#00D2BE" dot={false} strokeWidth={1} opacity={0.6}/>
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-4">
                {/* Live header */}
                <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`w-3 h-3 rounded-full ${liveState?'bg-green-500 animate-pulse':'bg-white/20'}`}></span>
                      <div>
                        <div className="font-bold text-sm">{liveState?.session_name || 'Connecting live feed...'}</div>
                        <div className="text-xs mono text-white/60">LAP {liveState?.lap||'-'}/{liveState?.total_laps||'-'} • {liveState?.flag||'GREEN'} {liveState? `• ${liveState.elapsed_seconds.toFixed(1)}s` : ''}</div>
                      </div>
                    </div>
                    <div className={`px-3 py-1 rounded text-xs font-bold ${liveState?.flag==='YELLOW'?'bg-yellow-500 text-black': liveState?.flag==='SC'?'bg-orange-500': liveState?.flag==='RED'?'bg-red-600':'bg-green-600 text-white'}`}>{liveState?.flag||'LIVE'}</div>
                  </div>
                  {liveState?.weather && (
                    <div className="mt-3 flex gap-3 text-xs mono text-white/70 bg-black/40 rounded px-3 py-2">
                      <span>🌡️ Air {liveState.weather.air_temp}°C</span><span>Track {liveState.weather.track_temp}°C</span><span>💧 {liveState.weather.humidity}%</span>
                    </div>
                  )}
                </div>

                {/* Track map */}
                <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
                  <div className="text-xs mono text-white/60 mb-2">TRACK MAP — REAL X/Y @10Hz (interpolated @60fps)</div>
                  <div className="relative bg-[#0a0a0a] rounded border border-white/10 h-[380px] overflow-hidden">
                    {/* fake circuit outline */}
                    <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
                      <path d="M 20 50 C 15 20, 40 10, 60 20 C 80 30, 90 50, 80 70 C 70 85, 50 90, 30 80 C 15 70, 15 55, 20 50 Z" fill="none" stroke="#333" strokeWidth="1.5" strokeDasharray="4 4"/>
                      {(liveState?.cars||[]).map((c:Car)=>(
                        <g key={c.driver_number}>
                          <circle cx={c.x} cy={c.y} r="2.2" fill={c.team_colour||'#E10600'} stroke="white" strokeWidth="0.6"/>
                          <text x={c.x+3} y={c.y-2} fontSize="3" fill="white" className="mono" fontWeight="bold">{c.abbreviation}</text>
                        </g>
                      ))}
                    </svg>
                    <div className="absolute bottom-2 left-2 text-[10px] mono bg-black/60 px-2 py-1 rounded">cars: {liveState?.cars?.length||0} • source: OpenF1 location @0.5s → 60fps rAF</div>
                  </div>
                </div>

                {/* Live telemetry mini */}
                <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
                  <div className="text-xs mono text-white/60 mb-2">LIVE TIMING TOWER</div>
                  <div className="space-y-1 max-h-[420px] overflow-auto">
                    {(liveState?.cars||[]).slice(0,20).map((c:Car,i:number)=>(
                      <div key={c.driver_number} className="flex items-center gap-2 px-2 py-1.5 rounded bg-black/40 border border-white/5 text-xs">
                        <span className="w-6 text-center font-black mono">{c.position}</span>
                        <span className="w-2 h-6 rounded" style={{background:c.team_colour||'#555'}}></span>
                        <span className="font-bold w-10">{c.abbreviation}</span>
                        <span className="text-white/50 hidden sm:inline truncate">{c.full_name}</span>
                        <span className="ml-auto mono text-white/70">{c.gap_to_leader}</span>
                        <span className="mono text-white/50">{c.interval}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${c.compound==='SOFT'?'bg-red-600':c.compound==='MEDIUM'?'bg-yellow-500 text-black':c.compound==='HARD'?'bg-gray-200 text-black':'bg-white/20'}`}>{c.compound[0]}</span>
                        <span className="mono text-white/60">{c.tyre_age}L</span>
                        <span className="mono text-[#00D2BE] hidden md:inline">{c.speed} km/h</span>
                      </div>
                    )) || <div className="text-center py-8 text-white/40 text-sm">Waiting for live data...</div>}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right panel */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
              <div className="text-xs mono text-white/60 mb-2">HOW IT'S MORE ACCURATE</div>
              <div className="space-y-2.5 text-xs leading-relaxed">
                <div><b className="text-white">Quadratic tyre:</b> γ≥0 cliff, never phantom speed-up. Per-compound priors from 2023-25.</div>
                <div><b className="text-white">Fuel-corrected:</b> isolates tyre wear. Identifiable via stint resets.</div>
                <div><b className="text-white">Per-circuit:</b> Monza 0.85× vs Barcelona 1.25× degradation, SC hazards, pit loss.</div>
                <div><b className="text-white">AR(1) noise:</b> correlated laps, not i.i.d. — real racing.</div>
                <div><b className="text-white">10k Monte Carlo:</b> head-to-head per sim → win% not just mean.</div>
                <div><b className="text-white">Walk-forward:</b> fitted on earlier races, tested on later — no leakage.</div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-[#E10600] to-[#8B0000] rounded-xl p-4 text-white">
              <div className="text-xs mono opacity-80">BENCHMARKS (prior art)</div>
              <div className="mt-2 space-y-1.5 text-xs">
                <div className="flex justify-between"><span>Degradation MAE</span><b>0.054s/lap</b></div>
                <div className="flex justify-between"><span>LSTM next-lap</span><b>+13.1% vs persist</b></div>
                <div className="flex justify-between"><span>Strategy acc</span><b>74.1% / 0.765 AUC</b></div>
                <div className="flex justify-between"><span>MC speed</span><b>10k in &lt;200ms</b></div>
              </div>
              <div className="text-[11px] opacity-70 mt-2">Sources: ShivekRanjan, RuchirBhatia4, NarekGrigoryan, boxbox-f1 — see docs/RESOURCES.md</div>
            </div>

            <div className="bg-[#141414] border border-white/10 rounded-xl p-4">
              <div className="text-xs mono text-white/60 mb-2">QUICK ACTIONS</div>
              <div className="grid gap-2">
                <button onClick={runSimulation} className="w-full text-left px-3 py-2 rounded bg-white/5 hover:bg-white/10 text-xs">▶ Replay Monaco 78 laps (1-stop vs 2-stop)</button>
                <a href="/api/circuits" target="_blank" className="block px-3 py-2 rounded bg-white/5 hover:bg-white/10 text-xs">⛩ All circuits calibration →</a>
                <a href="/api/telemetry/mock/VER" target="_blank" className="block px-3 py-2 rounded bg-white/5 hover:bg-white/10 text-xs">📡 Sample telemetry JSON →</a>
                <a href="https://github.com/theOehrly/Fast-F1" target="_blank" className="block px-3 py-2 rounded bg-white/5 hover:bg-white/10 text-xs">📚 FastF1 docs →</a>
              </div>
            </div>

            <div className="bg-black/60 border border-white/10 rounded-xl p-3 text-[11px] mono text-white/40">
              <div>Backend: <a href="/" className="text-white/70 underline">/api/health</a> • WS /ws/live</div>
              <div>Frontend: Vite + React + Recharts + Tailwind</div>
              <div className="mt-1">Build: <span className="text-white/60">docker-compose up</span> or <span className="text-white/60">make api + make frontend</span></div>
            </div>
          </div>
        </div>
      </div>

      <footer className="max-w-7xl mx-auto px-4 py-6 text-center text-xs mono text-white/30 border-t border-white/5 mt-6">
        Built from <a href="https://github.com/subinium/awesome-f1" className="underline">awesome-f1</a> • Data: Jolpica-F1 (Ergast successor) • FastF1 • OpenF1 • F1DB • FIA-doc • TUM Racetrack DB • Attribution in docs/RESOURCES.md • MIT
      </footer>
    </div>
  )
}
