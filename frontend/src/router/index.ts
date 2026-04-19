import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/projects',
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('@/views/Projects.vue'),
    },
    {
      path: '/projects/:id',
      name: 'project-workspace',
      component: () => import('@/views/ProjectWorkspace.vue'),
    },
  ],
})

export default router
