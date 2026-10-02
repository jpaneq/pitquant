import { Component, type ReactNode } from 'react'

export class ErrorBoundary extends Component<{ children: ReactNode; what: string }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="rounded-md border border-down/30 bg-down/5 px-3 py-2 text-xs text-down">
          {this.props.what} failed to render: {this.state.error.message}
        </div>
      )
    }
    return this.props.children
  }
}
