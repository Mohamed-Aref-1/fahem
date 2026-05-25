import { useEffect, useRef } from 'react'

const NAVY  = [22, 47, 102]
const GOLD  = [212, 165, 0]
const GOLDB = [255, 210, 80]
const rgba  = ([r,g,b], a) => `rgba(${r},${g},${b},${a})`

/*
 * Low-poly brain mesh — fixed vertices that form a brain silhouette.
 * Normalized coords: center at (0,0), scaled by (rx, ry).
 * x: -1 = left (frontal lobe), +1 = right (occipital).
 * y: -1 = top (crown),          +1 = bottom (brainstem).
 *
 * Outer boundary: indices 0–16   Interior: indices 17–24
 */
const V = [
  /* ── outer boundary (clockwise from crown-left) ── */
  [-0.10, -1.00],  //  0  crown-left
  [ 0.28, -1.00],  //  1  crown-right
  [ 0.62, -0.80],  //  2  parietal top
  [ 0.88, -0.40],  //  3  occipital upper
  [ 0.98,  0.08],  //  4  occipital right
  [ 0.86,  0.50],  //  5  temporal right
  [ 0.55,  0.72],  //  6  temporal base (cerebrum–cerebellum notch)
  [ 0.62,  0.95],  //  7  cerebellum top
  [ 0.82,  1.00],  //  8  cerebellum right
  [ 0.55,  1.00],  //  9  cerebellum left
  [ 0.22,  0.88],  // 10  brainstem top
  [-0.08,  0.82],  // 11  base centre-left
  [-0.45,  0.62],  // 12  temporal left
  [-0.78,  0.30],  // 13  frontal lower
  [-0.95, -0.10],  // 14  frontal left (widest point)
  [-0.82, -0.56],  // 15  frontal upper-left
  [-0.48, -0.88],  // 16  frontal top
  /* ── interior ── */
  [-0.15, -0.55],  // 17  upper interior
  [ 0.32, -0.48],  // 18  upper-right interior
  [ 0.70,  0.05],  // 19  right interior
  [ 0.40,  0.45],  // 20  centre-right interior
  [-0.05,  0.42],  // 21  centre interior
  [-0.45,  0.10],  // 22  centre-left interior
  [-0.65, -0.25],  // 23  left interior
  [ 0.42,  0.88],  // 24  cerebellum interior
]

/* Triangulated edge list — derived to fill every region of the mesh */
const EDGES = [
  /* outer boundary */
  [0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[7,8],[8,9],[9,10],
  [10,11],[11,12],[12,13],[13,14],[14,15],[15,16],[16,0],
  /* spokes: boundary → interior */
  [0,17],[0,18],[1,18],[2,18],[2,19],[3,19],[4,19],[5,19],[5,20],
  [6,20],[6,24],[7,24],[8,24],[9,24],[10,24],[10,21],[11,21],
  [12,21],[12,22],[13,22],[14,23],[15,23],[16,23],[16,17],[15,17],
  /* interior cross-connections */
  [17,18],[17,22],[17,23],[18,19],[18,20],[18,21],
  [19,20],[20,21],[20,24],[21,22],[21,24],[22,23],
  /* cerebellum shortcuts */
  [6,10],[7,9],
]

export default function NeuralBrain({ className = '', style = {} }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId
    let verts  = []  // scaled pixel positions
    let nodes  = []  // per-vertex activation state
    let pulses = []

    const setup = () => {
      const dpr = window.devicePixelRatio || 1
      const W   = canvas.offsetWidth
      const H   = canvas.offsetHeight
      canvas.width  = W * dpr
      canvas.height = H * dpr
      ctx.scale(dpr, dpr)

      /* Brain shifted LEFT so it sits behind the phone mockup */
      const cx = W * 0.30
      const cy = H * 0.43
      const rx = W * 0.28
      const ry = H * 0.40

      verts = V.map(([nx, ny]) => ({ x: cx + nx * rx, y: cy + ny * ry }))
      nodes = verts.map(() => ({ activation: 0, decay: 0.012 + Math.random() * 0.010 }))
      pulses = []
      for (let i = 0; i < 8; i++) spawnPulse()
    }

    const spawnPulse = () => {
      const ei = Math.random() * EDGES.length | 0
      pulses.push({ ei, progress: 0, speed: 0.006 + Math.random() * 0.006, forward: Math.random() > 0.5 })
    }

    const spawnTimer = setInterval(() => { if (pulses.length < 28) spawnPulse() }, 380)

    const draw = () => {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      ctx.clearRect(0, 0, W, H)

      /* edges */
      for (const [ai, bi] of EDGES) {
        const a   = verts[ai], b = verts[bi]
        const act = Math.max(nodes[ai].activation, nodes[bi].activation)
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        if (act > 0.05) {
          ctx.strokeStyle = rgba(GOLD, 0.35 + act * 0.55)
          ctx.lineWidth   = 1.5 + act * 1.8
        } else {
          ctx.strokeStyle = rgba(NAVY, 0.42)
          ctx.lineWidth   = 1.3
        }
        ctx.stroke()
      }

      /* pulses */
      for (const p of pulses) {
        const [ai, bi] = EDGES[p.ei]
        const a  = verts[ai], b = verts[bi]
        const t  = p.forward ? p.progress : 1 - p.progress
        const px = a.x + (b.x - a.x) * t
        const py = a.y + (b.y - a.y) * t

        const halo = ctx.createRadialGradient(px, py, 0, px, py, 16)
        halo.addColorStop(0,   rgba(GOLDB, 0.88))
        halo.addColorStop(0.4, rgba(GOLD,  0.42))
        halo.addColorStop(1,   rgba(GOLD,  0))
        ctx.beginPath(); ctx.arc(px, py, 16, 0, Math.PI * 2)
        ctx.fillStyle = halo; ctx.fill()

        ctx.beginPath(); ctx.arc(px, py, 3.5, 0, Math.PI * 2)
        ctx.fillStyle = rgba(GOLDB, 1); ctx.fill()
      }

      /* nodes */
      for (let i = 0; i < verts.length; i++) {
        const v = verts[i], n = nodes[i]
        const r = n.activation > 0.08 ? 4.5 : 3.8
        if (n.activation > 0.04) {
          const g = ctx.createRadialGradient(v.x, v.y, 0, v.x, v.y, r * 3.5)
          g.addColorStop(0, rgba(GOLD, n.activation * 0.85))
          g.addColorStop(1, rgba(GOLD, 0))
          ctx.beginPath(); ctx.arc(v.x, v.y, r * 3.5, 0, Math.PI * 2)
          ctx.fillStyle = g; ctx.fill()
        }
        ctx.beginPath(); ctx.arc(v.x, v.y, r, 0, Math.PI * 2)
        ctx.fillStyle = n.activation > 0.08 ? rgba(GOLDB, 1) : rgba(NAVY, 0.72)
        ctx.fill()
      }

      /* advance pulses + cascade to neighbours */
      for (let i = pulses.length - 1; i >= 0; i--) {
        pulses[i].progress += pulses[i].speed
        if (pulses[i].progress >= 1) {
          const [ai, bi] = EDGES[pulses[i].ei]
          const target   = pulses[i].forward ? bi : ai
          nodes[target].activation = 1

          if (pulses.length < 24) {
            const out = EDGES
              .map((e, ei) => ({ e, ei }))
              .filter(({ e, ei }) => ei !== pulses[i].ei && (e[0] === target || e[1] === target))
              .sort(() => Math.random() - 0.5)
              .slice(0, Math.random() > 0.5 ? 2 : 1)
            for (const { e, ei } of out)
              pulses.push({ ei, progress: 0, speed: 0.006 + Math.random() * 0.006, forward: e[0] === target })
          }
          pulses.splice(i, 1)
        }
      }

      /* decay */
      for (const n of nodes)
        if (n.activation > 0) n.activation = Math.max(0, n.activation - n.decay)

      animId = requestAnimationFrame(draw)
    }

    setup()
    draw()
    const onResize = () => setup()
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(animId)
      clearInterval(spawnTimer)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full pointer-events-none ${className}`}
      style={style}
    />
  )
}
