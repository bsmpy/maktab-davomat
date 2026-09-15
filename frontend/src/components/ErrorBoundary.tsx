import { Component, type ErrorInfo, type ReactNode } from 'react'
import i18n from '@/i18n'

import { Button } from './ui'

interface State {
  error: Error | null
}

/** Last line of defence: a render crash shows a recoverable screen, not a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error('Unhandled render error', error, info)
    }
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="grid min-h-dvh place-items-center bg-ink-50 px-6">
        <div className="card w-full max-w-md p-8 text-center">
          <h1 className="text-lg font-semibold text-ink-900">{i18n.t('common.somethingWrong')}</h1>
          <p className="mt-2 text-sm text-ink-500">
            {i18n.t('common.somethingWrongHint')}
          </p>
          <Button className="mt-6" onClick={() => window.location.reload()}>
            {i18n.t('common.reloadPage')}
          </Button>
        </div>
      </div>
    )
  }
}
