import Hls from 'hls.js'
import { ref, onUnmounted, type Ref } from 'vue'

export function useHlsPlayer(videoRef: Ref<HTMLVideoElement | null>, playlistUrl: string) {
  const currentSegment = ref<string | null>(null)
  const isStreamActive = ref(false)

  let hls: Hls | null = null

  function setup() {
    const video = videoRef.value
    if (!video) return

    video.muted = true
    video.autoplay = true

    if (Hls.isSupported()) {
      hls = new Hls()
      hls.loadSource(playlistUrl)
      hls.attachMedia(video)

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        isStreamActive.value = true
        const playPromise = video.play()
        if (playPromise && typeof playPromise.catch === 'function') {
          playPromise.catch((err: unknown) => {
            console.debug('Autoplay prevented, waiting for user gesture.', err)
          })
        }
      })

      hls.on(Hls.Events.FRAG_CHANGED, (_event, data) => {
        if (data.frag && data.frag.url) {
          const url = data.frag.url
          const filename = url.substring(url.lastIndexOf('/') + 1)
          currentSegment.value = filename
        }
      })

      hls.on(Hls.Events.ERROR, (_event, data) => {
        console.error('HLS Error:', data)
        if (data.fatal) {
          isStreamActive.value = false
        }
      })

      return
    }

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = playlistUrl
      video.addEventListener('loadedmetadata', () => {
        isStreamActive.value = true
        const playPromise = video.play()
        if (playPromise && typeof playPromise.catch === 'function') {
          playPromise.catch((err: unknown) => {
            console.debug('Autoplay prevented, waiting for user gesture.', err)
          })
        }
      })
      return
    }

    console.error('HLS not supported in this browser.')
  }

  onUnmounted(() => {
    hls?.destroy()
    hls = null
  })

  return { currentSegment, isStreamActive, setup }
}
