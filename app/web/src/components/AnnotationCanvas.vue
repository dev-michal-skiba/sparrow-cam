<template>
  <div
    ref="overlayRef"
    class="overlay"
    :class="{ 'overlay--picking': !!pickerRect }"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    @pointerleave="onPointerLeave"
  >
    <div v-if="mousePos && !dragStart && !pickerRect" class="helpline helpline--h" :style="{ top: `${mousePos.y}px` }"></div>
    <div v-if="mousePos && !dragStart && !pickerRect" class="helpline helpline--v" :style="{ left: `${mousePos.x}px` }"></div>

    <div
      v-for="(roi, i) in annotations"
      :key="`${i}-${roi.bird_class}-${roi.bbox.x}-${roi.bbox.y}`"
      class="roi"
      :style="roiStyle(roi.bbox)"
    >
      <span class="roi-label">{{ unslugBird(roi.bird_class) }}</span>
      <button
        type="button"
        class="roi-remove"
        title="Remove annotation"
        @pointerdown.stop
        @click.stop="$emit('remove', i)"
      >×</button>
    </div>

    <div v-if="dragBox" class="roi roi--drag" :style="dragBoxStyle"></div>

    <div v-if="pickerRect" class="picker" :style="pickerStyle" @pointerdown.stop>
      <div class="picker-title">Pick a bird</div>
      <button
        v-for="bird in BIRD_TYPES"
        :key="bird"
        type="button"
        class="picker-btn"
        @click="confirmPicker(bird)"
      >{{ bird }}</button>
      <button type="button" class="picker-cancel" @click="cancelPicker">Cancel</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { BIRD_TYPES, BIRD_SLUGS, unslugBird, type BirdType } from '../composables/useBirdFilter'
import type { BoundingBox, ROIAnnotation } from '../types/annotations'

defineProps<{
  annotations: ROIAnnotation[]
}>()

const emit = defineEmits<{
  add: [roi: ROIAnnotation]
  remove: [index: number]
}>()

const overlayRef = ref<HTMLDivElement | null>(null)

interface PixelRect {
  left: number
  top: number
  width: number
  height: number
}

const dragStart = ref<{ x: number; y: number } | null>(null)
const dragBox = ref<PixelRect | null>(null)
const pickerRect = ref<PixelRect | null>(null)
const mousePos = ref<{ x: number; y: number } | null>(null)

const MIN_NORMALIZED_SIZE = 0.01

function clientToLocal(event: PointerEvent): { x: number; y: number } | null {
  const el = overlayRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(event.clientX - rect.left, rect.width)),
    y: Math.max(0, Math.min(event.clientY - rect.top, rect.height)),
  }
}

function rectFromPoints(a: { x: number; y: number }, b: { x: number; y: number }): PixelRect {
  return {
    left: Math.min(a.x, b.x),
    top: Math.min(a.y, b.y),
    width: Math.abs(b.x - a.x),
    height: Math.abs(b.y - a.y),
  }
}

function onPointerDown(event: PointerEvent) {
  if (pickerRect.value) return
  if (event.button !== 0 && event.pointerType === 'mouse') return
  const local = clientToLocal(event)
  if (!local) return
  dragStart.value = local
  dragBox.value = { left: local.x, top: local.y, width: 0, height: 0 }
  overlayRef.value?.setPointerCapture(event.pointerId)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  const local = clientToLocal(event)
  if (!local) return
  mousePos.value = local
  if (!dragStart.value) return
  dragBox.value = rectFromPoints(dragStart.value, local)
}

function onPointerLeave() {
  mousePos.value = null
}

function onPointerUp(event: PointerEvent) {
  if (!dragStart.value || !dragBox.value) {
    dragStart.value = null
    dragBox.value = null
    return
  }
  const overlay = overlayRef.value
  const rect = overlay?.getBoundingClientRect()
  const finalBox = dragBox.value
  dragStart.value = null

  if (overlay && overlay.hasPointerCapture(event.pointerId)) {
    overlay.releasePointerCapture(event.pointerId)
  }

  if (!rect || rect.width === 0 || rect.height === 0) {
    dragBox.value = null
    return
  }

  const normalizedW = finalBox.width / rect.width
  const normalizedH = finalBox.height / rect.height
  if (normalizedW < MIN_NORMALIZED_SIZE || normalizedH < MIN_NORMALIZED_SIZE) {
    dragBox.value = null
    return
  }

  pickerRect.value = finalBox
}

function onPointerCancel() {
  dragStart.value = null
  dragBox.value = null
}

function confirmPicker(bird: BirdType) {
  const rectPx = pickerRect.value
  const overlay = overlayRef.value
  if (!rectPx || !overlay) {
    cancelPicker()
    return
  }
  const overlayRect = overlay.getBoundingClientRect()
  if (overlayRect.width === 0 || overlayRect.height === 0) {
    cancelPicker()
    return
  }

  let x = rectPx.left / overlayRect.width
  let y = rectPx.top / overlayRect.height
  let width = rectPx.width / overlayRect.width
  let height = rectPx.height / overlayRect.height

  x = Math.max(0, Math.min(x, 1))
  y = Math.max(0, Math.min(y, 1))
  if (x + width > 1) width = 1 - x
  if (y + height > 1) height = 1 - y

  if (width <= 0 || height <= 0) {
    cancelPicker()
    return
  }

  const bbox: BoundingBox = { x, y, width, height }
  emit('add', { bird_class: BIRD_SLUGS[bird] as ROIAnnotation['bird_class'], bbox })
  cancelPicker()
}

function cancelPicker() {
  pickerRect.value = null
  dragBox.value = null
}

function onWindowKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && pickerRect.value) {
    cancelPicker()
    event.stopPropagation()
  }
}

function onWindowPointerDown(event: PointerEvent) {
  if (!pickerRect.value) return
  const overlay = overlayRef.value
  if (!overlay) return
  if (!overlay.contains(event.target as Node)) {
    cancelPicker()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onWindowKey)
  window.addEventListener('pointerdown', onWindowPointerDown, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKey)
  window.removeEventListener('pointerdown', onWindowPointerDown, true)
})

function roiStyle(bbox: BoundingBox) {
  return {
    left: `${bbox.x * 100}%`,
    top: `${bbox.y * 100}%`,
    width: `${bbox.width * 100}%`,
    height: `${bbox.height * 100}%`,
  }
}

const dragBoxStyle = computed(() => {
  if (!dragBox.value) return {}
  return {
    left: `${dragBox.value.left}px`,
    top: `${dragBox.value.top}px`,
    width: `${dragBox.value.width}px`,
    height: `${dragBox.value.height}px`,
  }
})

const pickerStyle = computed(() => {
  if (!pickerRect.value || !overlayRef.value) return {}
  const overlay = overlayRef.value.getBoundingClientRect()
  const rect = pickerRect.value
  const popoverWidth = 160
  const popoverHeight = 200
  let left = rect.left + rect.width
  let top = rect.top + rect.height
  if (left + popoverWidth > overlay.width) {
    left = Math.max(0, overlay.width - popoverWidth)
  }
  if (top + popoverHeight > overlay.height) {
    top = Math.max(0, rect.top - popoverHeight)
  }
  return { left: `${left}px`, top: `${top}px` }
})
</script>

<style scoped>
.overlay {
  position: absolute;
  inset: 0;
  touch-action: none;
  cursor: crosshair;
  user-select: none;
}

.overlay--picking {
  cursor: default;
}

.helpline {
  position: absolute;
  pointer-events: none;
  opacity: 0.5;
  background: var(--secondary-color);
}

.helpline--h {
  left: 0;
  right: 0;
  height: 1px;
  transform: translateY(-50%);
}

.helpline--v {
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

.roi {
  position: absolute;
  border: 2px solid var(--secondary-color);
  background: rgba(3, 182, 3, 0.18);
  box-sizing: border-box;
  pointer-events: auto;
}

.roi--drag {
  border-style: dashed;
  background: rgba(3, 182, 3, 0.1);
  pointer-events: none;
}

.roi-label {
  position: absolute;
  top: -1.5rem;
  left: -2px;
  padding: 1px 6px;
  background: var(--secondary-color);
  color: #022c22;
  font-size: 0.75rem;
  font-weight: 700;
  border-radius: 3px;
  white-space: nowrap;
}

.roi-remove {
  position: absolute;
  top: -10px;
  right: -10px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid var(--secondary-color);
  background: #022c22;
  color: var(--secondary-color);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.roi-remove:hover {
  background: var(--secondary-color);
  color: #022c22;
}

.picker {
  position: absolute;
  width: 160px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: #0f172a;
  border: 1px solid rgba(3, 182, 3, 0.4);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 10;
}

.picker-title {
  font-size: 0.75rem;
  opacity: 0.7;
  margin-bottom: 2px;
}

.picker-btn,
.picker-cancel {
  font-family: inherit;
  font-size: 0.85rem;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: var(--primary-color);
}

.picker-btn:hover {
  background: rgba(3, 182, 3, 0.18);
  border-color: var(--secondary-color);
}

.picker-cancel {
  margin-top: 4px;
  opacity: 0.7;
}

.picker-cancel:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.05);
}
</style>
