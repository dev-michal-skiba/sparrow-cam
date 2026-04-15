import { ref, watchEffect, type Ref } from 'vue'

interface AdjacentRecording {
  year: string
  month: string
  day: string
  stream: string
}

interface AdjacentResult {
  previous: AdjacentRecording | null
  next: AdjacentRecording | null
}

export function useArchiveAdjacent(
  year: string,
  month: string,
  day: string,
  stream: string,
  birdsParam?: Ref<string>,
) {
  const previous = ref<AdjacentRecording | null>(null)
  const next = ref<AdjacentRecording | null>(null)

  watchEffect(async () => {
    const birds = birdsParam?.value ?? ''
    try {
      const params = new URLSearchParams({ year, month, day, stream })
      if (birds) params.set('birds', birds)
      const response = await fetch(`/archive/api/adjacent?${params}`)
      if (!response.ok) {
        previous.value = null
        next.value = null
        return
      }
      const data: AdjacentResult = await response.json()
      previous.value = data.previous
      next.value = data.next
    } catch {
      // leave as null
    }
  })

  return { previous, next }
}
