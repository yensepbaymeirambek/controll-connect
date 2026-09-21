import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/api'

export interface Resource<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

/** Loads a resource on mount, aborts in flight requests, and can reload on demand. */
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  const run = useCallback(() => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setLoading(true)
    load(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setData(result)
        setError(null)
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return
        setError(caught instanceof ApiError ? caught.message : 'Unexpected error')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [load])

  useEffect(() => {
    // Fetching on mount is the point of this hook; `loading` already starts true,
    // so the synchronous setState the rule warns about changes nothing on mount.
    // eslint-disable-next-line react/set-state-in-effect
    run()
    return () => controllerRef.current?.abort()
  }, [run])

  return { data, loading, error, reload: run }
}
