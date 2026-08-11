import { useState } from 'react'
import { SpinnerGap, Warehouse } from '@phosphor-icons/react'
import { api, saveSession } from '../api'
import { useNotify, ToastStack } from '../hooks/useNotify'

export default function LoginPage({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { toasts, notify, dismiss, pauseToast, resumeToast } = useNotify()

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    try {
      const data = await api.login(username, password)
      saveSession(data)
      onSuccess(data.user)
    } catch (err) {
      notify(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <ToastStack toasts={toasts} dismiss={dismiss} pauseToast={pauseToast} resumeToast={resumeToast} />
      <section className="login-aside">
        <div className="brand"><span className="brand-mark"><Warehouse size={22} weight="fill" /></span><span>smart.<b>ombor</b></span></div>
        <div className="login-copy">
          <p className="eyebrow">BIR TIZIM, TO‘LIQ NAZORAT</p>
          <h1>Ombor, hujjat va hisoblar bir joyda.</h1>
          <p>Har bir buyurtma, qoldiq va to‘lovning holatini real vaqtda kuzating.</p>
        </div>
        <div className="aside-footer"><span className="live-dot" />Tizim ishlayapti</div>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <p className="eyebrow">XUSH KELIBSIZ</p>
          <h2>Hisobingizga kiring</h2>
          <p className="muted">Davom etish uchun login ma’lumotlaringizni kiriting.</p>
          <label>Login<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></label>
          <label>Parol<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
          <button className="primary-button" disabled={loading}>
            {loading ? <span className="btn-skeleton" aria-hidden="true" /> : 'Tizimga kirish'}
          </button>
          <p className="form-footnote">Kirish huquqi administrator tomonidan beriladi.</p>
        </form>
      </section>
    </main>
  )
}
