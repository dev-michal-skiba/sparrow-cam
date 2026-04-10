import { createRouter, createWebHistory } from 'vue-router'
import LiveView from '../views/LiveView.vue'
import ArchiveView from '../views/ArchiveView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: LiveView },
    { path: '/archive', component: ArchiveView },
  ],
})

export default router
