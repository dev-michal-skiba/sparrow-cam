import { ref, computed } from 'vue'
import type { ManualAnnotationsMap, ROIAnnotation } from '../types/annotations'

interface SubmitParams {
  year: string
  month: string
  day: string
  stream: string
}

export function useManualAnnotations() {
  const annotations = ref<ManualAnnotationsMap>({})
  const initialSnapshot = ref<string>('{}')
  const loaded = ref<boolean | null>(null)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  const lastSubmitOk = ref(false)

  function snapshot(): string {
    return JSON.stringify(annotations.value)
  }

  async function load(metaUrl: string) {
    try {
      const response = await fetch(metaUrl, { cache: 'no-store' })
      if (!response.ok) {
        annotations.value = {}
        initialSnapshot.value = snapshot()
        loaded.value = false
        return
      }
      const meta = await response.json()
      const existing: ManualAnnotationsMap = (meta && meta.manual_annotations) || {}
      annotations.value = JSON.parse(JSON.stringify(existing))
      initialSnapshot.value = snapshot()
      loaded.value = true
    } catch {
      annotations.value = {}
      initialSnapshot.value = snapshot()
      loaded.value = false
    }
  }

  function getForSegment(segment: string): ROIAnnotation[] {
    return annotations.value[segment] ?? []
  }

  function addRoi(segment: string, roi: ROIAnnotation) {
    const next = { ...annotations.value }
    const list = next[segment] ? [...next[segment]] : []
    list.push(roi)
    next[segment] = list
    annotations.value = next
  }

  function removeRoi(segment: string, index: number) {
    const current = annotations.value[segment]
    if (!current) return
    const next = { ...annotations.value }
    const list = current.filter((_, i) => i !== index)
    if (list.length === 0) {
      delete next[segment]
    } else {
      next[segment] = list
    }
    annotations.value = next
  }

  const isDirty = computed(() => snapshot() !== initialSnapshot.value)

  async function submit(params: SubmitParams) {
    submitting.value = true
    error.value = null
    lastSubmitOk.value = false

    const payload: ManualAnnotationsMap = {}
    for (const [segment, list] of Object.entries(annotations.value)) {
      if (list && list.length > 0) {
        payload[segment] = list
      }
    }

    const url = `/archive/api/meta?year=${encodeURIComponent(params.year)}&month=${encodeURIComponent(params.month)}&day=${encodeURIComponent(params.day)}&stream=${encodeURIComponent(params.stream)}`

    try {
      const response = await fetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manual_annotations: payload }),
      })
      if (!response.ok) {
        const text = await response.text().catch(() => '')
        error.value = `Submit failed (${response.status})${text ? `: ${text}` : ''}`
        return false
      }
      initialSnapshot.value = snapshot()
      lastSubmitOk.value = true
      return true
    } catch (e) {
      error.value = `Submit failed: ${(e as Error).message ?? 'network error'}`
      return false
    } finally {
      submitting.value = false
    }
  }

  return {
    annotations,
    loaded,
    submitting,
    error,
    lastSubmitOk,
    isDirty,
    load,
    getForSegment,
    addRoi,
    removeRoi,
    submit,
  }
}
