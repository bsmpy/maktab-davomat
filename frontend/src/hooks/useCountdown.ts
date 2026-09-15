import { useCallback, useEffect, useState } from 'react'

/** Seconds-remaining counter used by the OTP resend button. */
export function useCountdown(initial = 0): [number, (seconds: number) => void] {
  const [remaining, setRemaining] = useState(initial)

  useEffect(() => {
    if (remaining <= 0) return
    const timer = window.setInterval(() => {
      setRemaining((value) => (value <= 1 ? 0 : value - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [remaining])

  const start = useCallback((seconds: number) => setRemaining(seconds), [])
  return [remaining, start]
}
