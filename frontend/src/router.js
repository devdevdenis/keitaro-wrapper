import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: { name: 'campaigns' } },
  {
    path: '/campaigns',
    name: 'campaigns',
    component: () => import('@/views/CampaignsView.vue'),
    meta: { title: 'Кампании' },
  },
  {
    path: '/campaigns/new',
    name: 'campaign-create',
    component: () => import('@/views/CampaignCreateView.vue'),
    meta: { title: 'Новая кампания' },
  },
  {
    path: '/campaigns/:id(\\d+)',
    name: 'campaign-edit',
    component: () => import('@/views/CampaignEditView.vue'),
    props: (route) => ({ id: Number(route.params.id) }),
    meta: { title: 'Редактор кампании' },
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'campaigns' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Keitaro Wrapper` : 'Keitaro Wrapper'
})

export default router
