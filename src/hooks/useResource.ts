import { useEffect, useState } from 'react'
import { ApiError } from '../lib/api'

export interface Resource<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/** Loads a resource once on mount and aborts the request on unmount. */
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ data: null, loading: true, error: null })

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ data: null, loading: false, error: error instanceof ApiError ? error.message : 'Unexpected error' })
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return state
}
