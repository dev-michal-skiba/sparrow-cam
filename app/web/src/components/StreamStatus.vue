<template>
  <div class="stream-status">
    <span class="dot" :class="isStreamActive ? 'dot-live' : 'dot-offline'"></span>
    <span class="status-text" :class="isStreamActive ? 'text-live' : 'text-offline'">
      {{ isStreamActive ? 'Live' : 'Offline' }}
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  isStreamActive: boolean
}>()
</script>

<style scoped>
.stream-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-live {
  background: #ef4444;
}

.dot-offline {
  background: #6b7280;
}

.status-text {
  font-size: 16px;
  font-weight: 500;
}

.text-live {
  color: #ffffff;
}

.text-offline {
  color: #6b7280;
}
</style>
