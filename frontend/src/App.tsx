import { useEffect, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Stars } from '@react-three/drei'
import { motion, AnimatePresence } from 'framer-motion'
import { ArcReactor } from './components/ArcReactor'
import { Waveform } from './components/Waveform'

const SESSION_ID = crypto.randomUUID()

type Status = 'idle' | 'listening' | 'thinking' | 'speaking'

interface Message {
  role: 'user' | 'jarvis'
  text: string
}

export default function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [messages, setMessages] = useState<Message[]>([])
  const [currentToken, setCurrentToken] = useState('')
  const [alerts, setAlerts] = useState<string[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/voice/${SESSION_ID}`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'thinking') {
        setStatus('thinking')
        setCurrentToken('')
      } else if (msg.type === 'token') {
        setStatus('speaking')
        setCurrentToken(prev => prev + msg.text)
      } else if (msg.type === 'done') {
        setMessages(prev => [...prev, { role: 'jarvis', text: msg.text }])
        setCurrentToken('')
        setStatus('idle')
      } else if (msg.type === 'alert') {
        setAlerts(prev => [...prev.slice(-4), msg.text])
      }
    }

    ws.onclose = () => setStatus('idle')
    return () => ws.close()
  }, [])

  const sendText = (text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    setMessages(prev => [...prev, { role: 'user', text }])
    setStatus('thinking')
    wsRef.current.send(JSON.stringify({ type: 'transcript', text }))
  }

  return (
    <div style={styles.container}>
      {/* Three.js Arc Reactor */}
      <div style={styles.reactor}>
        <Canvas camera={{ position: [0, 0, 5] }}>
          <ambientLight intensity={0.2} />
          <pointLight position={[0, 0, 3]} intensity={2} color="#00d4ff" />
          <Stars radius={50} depth={50} count={2000} factor={2} />
          <ArcReactor active={status !== 'idle'} speaking={status === 'speaking'} />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
        </Canvas>
      </div>

      {/* Status */}
      <div style={styles.statusRow}>
        <span style={{ ...styles.statusDot, background: STATUS_COLORS[status] }} />
        <span style={styles.statusText}>JARVIS · {status.toUpperCase()}</span>
      </div>

      {/* Waveform */}
      <div style={styles.waveformWrap}>
        <Waveform active={status !== 'idle'} speaking={status === 'speaking'} />
      </div>

      {/* Streaming token display */}
      <AnimatePresence>
        {currentToken && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={styles.streamBox}
          >
            {currentToken}
            <span style={styles.cursor}>▋</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Conversation log */}
      <div style={styles.log}>
        {messages.slice(-6).map((m, i) => (
          <div key={i} style={{ ...styles.msg, ...(m.role === 'user' ? styles.userMsg : styles.jarvisMsg) }}>
            <span style={styles.msgRole}>{m.role === 'user' ? 'YOU' : 'JARVIS'}</span>
            <span>{m.text}</span>
          </div>
        ))}
      </div>

      {/* Alerts */}
      <div style={styles.alerts}>
        {alerts.map((a, i) => (
          <motion.div key={i} initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} style={styles.alert}>
            ⚡ {a}
          </motion.div>
        ))}
      </div>

      {/* Text input fallback */}
      <TextInput onSend={sendText} disabled={status !== 'idle'} />
    </div>
  )
}

function TextInput({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [val, setVal] = useState('')
  return (
    <div style={styles.inputRow}>
      <input
        style={styles.input}
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && val.trim()) { onSend(val.trim()); setVal('') } }}
        placeholder="Type a command or question..."
        disabled={disabled}
      />
      <button style={styles.btn} onClick={() => { if (val.trim()) { onSend(val.trim()); setVal('') } }} disabled={disabled}>
        Send
      </button>
    </div>
  )
}

const STATUS_COLORS: Record<Status, string> = {
  idle: '#334',
  listening: '#00ff88',
  thinking: '#ffaa00',
  speaking: '#00d4ff',
}

const styles: Record<string, React.CSSProperties> = {
  container: { background: '#050a14', minHeight: '100vh', color: '#cce8ff', fontFamily: 'monospace', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px 16px', gap: 16 },
  reactor: { width: 280, height: 280 },
  statusRow: { display: 'flex', alignItems: 'center', gap: 8 },
  statusDot: { width: 10, height: 10, borderRadius: '50%', transition: 'background 0.3s' },
  statusText: { fontSize: 12, letterSpacing: '0.15em', color: '#5599cc' },
  waveformWrap: { width: '100%', maxWidth: 600 },
  streamBox: { maxWidth: 600, width: '100%', background: 'rgba(0,180,255,0.07)', border: '1px solid rgba(0,180,255,0.2)', borderRadius: 8, padding: '12px 16px', fontSize: 15, lineHeight: 1.6 },
  cursor: { animation: 'blink 1s step-end infinite' },
  log: { width: '100%', maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 8 },
  msg: { padding: '8px 12px', borderRadius: 8, fontSize: 13, lineHeight: 1.5, display: 'flex', flexDirection: 'column', gap: 2 },
  userMsg: { background: 'rgba(255,255,255,0.04)', borderLeft: '2px solid #334' },
  jarvisMsg: { background: 'rgba(0,180,255,0.06)', borderLeft: '2px solid #00d4ff' },
  msgRole: { fontSize: 10, letterSpacing: '0.1em', opacity: 0.5 },
  alerts: { position: 'fixed', top: 20, right: 20, display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 320 },
  alert: { background: 'rgba(255,170,0,0.12)', border: '1px solid rgba(255,170,0,0.3)', borderRadius: 8, padding: '8px 12px', fontSize: 13 },
  inputRow: { display: 'flex', gap: 8, width: '100%', maxWidth: 600 },
  input: { flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,180,255,0.2)', borderRadius: 8, padding: '10px 14px', color: '#cce8ff', fontSize: 14, outline: 'none' },
  btn: { background: 'rgba(0,180,255,0.15)', border: '1px solid rgba(0,180,255,0.3)', borderRadius: 8, padding: '10px 20px', color: '#00d4ff', cursor: 'pointer', fontSize: 14 },
}
