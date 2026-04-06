import { useEffect, useRef } from 'react'

interface WaveformProps {
  active: boolean
  speaking: boolean
}

export function Waveform({ active, speaking }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const phaseRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const draw = () => {
      const { width, height } = canvas
      ctx.clearRect(0, 0, width, height)

      if (!active && !speaking) {
        // Flat idle line
        ctx.strokeStyle = 'rgba(0, 180, 255, 0.3)'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(0, height / 2)
        ctx.lineTo(width, height / 2)
        ctx.stroke()
        animRef.current = requestAnimationFrame(draw)
        return
      }

      phaseRef.current += speaking ? 0.12 : 0.06
      const bars = 64
      const barW = width / bars

      for (let i = 0; i < bars; i++) {
        const t = i / bars
        const amp = speaking
          ? Math.sin(t * Math.PI * 6 + phaseRef.current) * 0.5 + Math.random() * 0.5
          : Math.sin(t * Math.PI * 4 + phaseRef.current) * 0.3
        const barH = Math.abs(amp) * (height * 0.8)
        const alpha = 0.4 + Math.abs(amp) * 0.6

        ctx.fillStyle = speaking
          ? `rgba(0, 255, 200, ${alpha})`
          : `rgba(0, 180, 255, ${alpha})`
        ctx.fillRect(i * barW, (height - barH) / 2, barW - 1, barH)
      }

      animRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animRef.current)
  }, [active, speaking])

  return (
    <canvas
      ref={canvasRef}
      width={600}
      height={80}
      style={{ width: '100%', height: 80, borderRadius: 8 }}
    />
  )
}
