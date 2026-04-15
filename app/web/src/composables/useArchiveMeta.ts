import { ref, computed, onMounted, type Ref } from 'vue'

interface Detection {
  class: string
  confidence: number
  roi: { x1: number; y1: number; x2: number; y2: number }
}

interface ArchiveMeta {
  version: number
  detections: Record<string, Detection[]>
}

export type { Detection }

export function useArchiveMeta(metaUrl: string, currentSegment: Ref<string | null>) {
  const meta = ref<ArchiveMeta | null>(null)
  const metaAvailable = ref<boolean | null>(null)

  onMounted(async () => {
    try {
      const response = await fetch(metaUrl)
      if (!response.ok) {
        metaAvailable.value = false
        return
      }
      meta.value = await response.json()
      metaAvailable.value = true
    } catch {
      metaAvailable.value = false
    }
  })

  const currentDetections = computed<Detection[]>(() => {
    if (!meta.value || !currentSegment.value) return []
    return meta.value.detections[currentSegment.value] ?? []
  })

  const streamBirds = computed<string[]>(() => {
    if (!meta.value) return []
    const birds = new Set<string>()
    for (const detections of Object.values(meta.value.detections)) {
      for (const det of detections) {
        birds.add(det.class)
      }
    }
    return [...birds].sort()
  })

  return { currentDetections, metaAvailable, streamBirds }
}
