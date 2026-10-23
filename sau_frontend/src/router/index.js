import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '总览' }
  },
  {
    path: '/publish',
    name: 'publish',
    component: () => import('@/views/PublishCenter.vue'),
    meta: { title: '发布中心' }
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('@/views/AccountManagement.vue'),
    meta: { title: '账号管理' }
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/views/Analytics.vue'),
    meta: { title: '数据分析' }
  },
  {
    path: '/materials',
    name: 'materials',
    component: () => import('@/views/MaterialManagement.vue'),
    meta: { title: '素材管理' }
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('@/views/About.vue'),
    meta: { title: '关于' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.afterEach((to) => {
  const title = to.meta && to.meta.title
  document.title = title ? title + ' · SAU 自媒体自动化' : 'SAU 自媒体自动化'
})

export default router
