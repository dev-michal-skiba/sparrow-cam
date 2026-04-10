<template>
  <p class="bird-status-text" :class="detected ? 'bird-text-on' : 'bird-text-off'">
    {{ detected ? 'Birds detected' : 'No birds detected' }}
  </p>
</template>

<script setup lang="ts">
defineProps<{
  detected: boolean
}>()
</script>

<style scoped>
.bird-status-text {
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}

.bird-text-off {
  color: #ffffff;
}

.bird-text-on {
  color: var(--secondary-color);
}
</style>
