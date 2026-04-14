import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue'
import type { Detection } from './useArchiveMeta'

interface AnnotationsFile {
  version: number
  detections: Record<string, Detection[]>
}

export function useAnnotations(currentSegment: Ref<string | null>) {
  const annotations = ref<AnnotationsFile | null>(null)
  const metaAvailable = ref<boolean | null>(null)

  const currentDetections = computed<Detection[]>(() => {
    if (!annotations.value || !currentSegment.value) return []
    return annotations.value.detections[currentSegment.value] ?? []
  })

  async function fetchAnnotations() {
    try {
      const response = await fetch('/annotations/bird.json', { cache: 'no-store' })
      if (!response.ok) {
        metaAvailable.value = false
        return
      }
      const data: AnnotationsFile = await response.json()
      annotations.value = data ?? null
      metaAvailable.value = true
    } catch {
      metaAvailable.value = false
    }
  }

  let intervalId: ReturnType<typeof setInterval>

  onMounted(() => {
    fetchAnnotations()
    intervalId = setInterval(fetchAnnotations, 500)
  })

  onUnmounted(() => {
    clearInterval(intervalId)
  })

  return { currentDetections, metaAvailable }
}
