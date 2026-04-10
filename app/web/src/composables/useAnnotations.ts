import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue'

interface Annotation {
  bird_detected: boolean
}

export function useAnnotations(currentSegment: Ref<string | null>) {
  const annotations = ref<Record<string, Annotation>>({})

  const isBirdDetected = computed(() => {
    if (!currentSegment.value) return false
    return annotations.value[currentSegment.value]?.bird_detected ?? false
  })

  async function fetchAnnotations() {
    try {
      const response = await fetch('/annotations/bird.json', { cache: 'no-store' })
      if (!response.ok) return
      const data: Record<string, Annotation> = await response.json()
      annotations.value = data ?? {}
    } catch (error) {
      console.error('Error fetching annotations:', error)
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

  return { isBirdDetected }
}
