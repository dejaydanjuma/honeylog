import { useCallback, useEffect, useState } from 'react'

const USER_ID = 'demo'

type Budget = {
  spent: number
  remaining: number
  daily_limit: number
  window_seconds: number
}

type SyncResponse = {
  noisy_histogram: Record<string, number>
  budget: Budget
}

const s = {
  page: {
    minHeight: '100vh',
    margin: 0,
    background: 'linear-gradient(135deg,#140d05,#2a1806 55%,#4a2b07)',
    color: '#fff7e2',
    fontFamily: 'Inter, system-ui, sans-serif',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  } as const,
  card: {
    width: '100%',
    maxWidth: 640,
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,208,92,0.25)',
    borderRadius: 20,
    padding: 32,
    boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
  } as const,
  label: { fontSize: 12, letterSpacing: 2, color: '#ffd36a', fontWeight: 700 } as const,
  h1: { fontSize: 40, margin: '8px 0 4px', fontWeight: 800, letterSpacing: -1 } as const,
  sub: { color: '#d6b77f', marginBottom: 28 } as const,
  track: {
    height: 18,
    borderRadius: 999,
    background: 'rgba(255,255,255,0.08)',
    overflow: 'hidden',
    margin: '16px 0 8px',
  } as const,
  fill: (pct: number, full: boolean) => ({
    height: '100%',
    width: `${pct}%`,
    borderRadius: 999,
    background: full
      ? 'linear-gradient(90deg,#f28c00,#ff6a3d)'
      : 'linear-gradient(90deg,#ffb020,#ffd36a)',
    transition: 'width 400ms ease, background 200ms ease',
  }),
  row: { display: 'flex', justifyContent: 'space-between', fontSize: 14, color: '#d6b77f' } as const,
  buttons: { display: 'flex', gap: 12, marginTop: 24, flexWrap: 'wrap' } as const,
  btn: (danger: boolean) =>
    ({
      flex: 1,
      minWidth: 140,
      padding: '14px 18px',
      borderRadius: 12,
      border: '1px solid rgba(255,208,92,0.35)',
      background: danger ? 'rgba(242,140,0,0.18)' : 'rgba(255,176,32,0.12)',
      color: '#ffe3a3',
      fontSize: 15,
      fontWeight: 600,
      cursor: 'pointer',
    }) as const,
  banner: (bad: boolean) =>
    ({
      marginTop: 20,
      padding: '14px 18px',
      borderRadius: 12,
      fontSize: 15,
      background: bad ? 'rgba(255,106,61,0.15)' : 'rgba(255,176,32,0.12)',
      border: `1px solid ${bad ? 'rgba(255,106,61,0.5)' : 'rgba(255,208,92,0.35)'}`,
      color: bad ? '#ffb59a' : '#ffe3a3',
    }) as const,
  hist: { marginTop: 20, fontSize: 14, color: '#d6b77f' } as const,
}

export default function App() {
  const [budget, setBudget] = useState<Budget | null>(null)
  const [last, setLast] = useState<SyncResponse | null>(null)
  const [message, setMessage] = useState<{ text: string; bad: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    const r = await fetch(`/api/ledger/${USER_ID}`)
    if (r.ok) setBudget(await r.json())
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function sync(epsilon: number) {
    setBusy(true)
    try {
      const r = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          user_id: USER_ID,
          histogram: { person: 4, commitment: 2, ambient: 9 },
          epsilon,
        }),
      })
      const body = await r.json()
      if (r.status === 429) {
        setMessage({
          text: `Refused — ${body.detail.available.toFixed(2)} ε remaining. The ledger fails closed.`,
          bad: true,
        })
        setLast(null)
        await refresh()
        return
      }
      setLast(body)
      setBudget(body.budget)
      setMessage({
        text: `Sync accepted — charged ${epsilon.toFixed(2)} ε.`,
        bad: false,
      })
    } finally {
      setBusy(false)
    }
  }

  const spent = budget?.spent ?? 0
  const limit = budget?.daily_limit ?? 0.8
  const pct = limit > 0 ? Math.min(100, (spent / limit) * 100) : 0
  const full = pct >= 99.5

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.label}>PRIVACY LEDGER</div>
        <h1 style={s.h1}>Honeylog</h1>
        <div style={s.sub}>Daily ε budget for user “{USER_ID}”</div>

        <div style={s.track}>
          <div style={s.fill(pct, full)} />
        </div>
        <div style={s.row}>
          <span>
            spent <strong style={{ color: '#fff7e2' }}>{spent.toFixed(2)}</strong> ε
          </span>
          <span>
            limit <strong style={{ color: '#fff7e2' }}>{limit.toFixed(2)}</strong> ε
          </span>
        </div>

        <div style={s.buttons}>
          <button style={s.btn(false)} disabled={busy} onClick={() => sync(0.4)}>
            Sync · ε 0.40
          </button>
          <button style={s.btn(true)} disabled={busy} onClick={() => sync(0.4)}>
            Sync · ε 0.40 (fill)
          </button>
          <button style={s.btn(true)} disabled={busy} onClick={() => sync(0.1)}>
            Sync · ε 0.10 (over)
          </button>
        </div>

        {message && <div style={s.banner(message.bad)}>{message.text}</div>}

        {last && (
          <div style={s.hist}>
            <strong style={{ color: '#ffe3a3' }}>Noisy histogram sent to AWS:</strong>
            <pre style={{ margin: '8px 0 0', color: '#ffd36a' }}>
              {JSON.stringify(last.noisy_histogram, null, 2)}
            </pre>
          </div>
        )}

        <div style={{ ...s.hist, marginTop: 24, fontSize: 12, opacity: 0.7 }}>
          Laplace mechanism · Δf = 1 · ε = {limit} · rolling window{' '}
          {budget ? Math.round(budget.window_seconds / 3600) : 24}h
        </div>
      </div>
    </div>
  )
}