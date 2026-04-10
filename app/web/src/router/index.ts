import { createRouter, createWebHistory } from 'vue-router'
import LiveView from '../views/LiveView.vue'
import ArchiveView from '../views/ArchiveView.vue'
import ArchivePlaybackView from '../views/ArchivePlaybackView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: LiveView },
    { path: '/archive', component: ArchiveView },
    { path: '/archive/:year/:month/:day/:stream', component: ArchivePlaybackView, name: 'archive-playback' },
  ],
})

export default router
