<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import ToastHost from '@/components/ToastHost.vue'
import { useHealth } from '@/composables/useHealth'

const { health } = useHealth()
const route = useRoute()

const connection = computed(() => {
  const mode = health.value?.keitaro
  if (!health.value) return { label: 'Проверка…', tone: 'slate' }
  if (health.value.status === 'down') return { label: 'Бэкенд недоступен', tone: 'red' }
  if (mode === 'live') return { label: 'Keitaro подключён', tone: 'green' }
  return { label: 'Keitaro не настроен', tone: 'red' }
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <RouterLink to="/" class="brand">
        <span class="brand-mark">K</span>
        <strong>Keitaro Wrapper</strong>
      </RouterLink>

      <nav class="nav">
        <!-- раздел активен и на создании, и в редакторе кампании -->
        <RouterLink
          :to="{ name: 'campaigns' }"
          class="nav-link"
          :class="{ active: route.path.startsWith('/campaigns') }"
        >
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M3 5h14M3 10h14M3 15h9" />
          </svg>
          Кампании
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <span class="badge" :class="`tone-${connection.tone}`">{{ connection.label }}</span>
        <span v-if="health?.keitaro_url && health.keitaro === 'live'" class="tracker-url">
          {{ health.keitaro_url.replace(/^https?:\/\//, '') }}
        </span>
      </div>
    </aside>

    <main class="main">
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" :key="route.fullPath" />
      </RouterView>
    </main>

    <ToastHost />
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px 14px;
  background: var(--sidebar);
  color: var(--sidebar-text);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 22px;
  color: #fff;
  text-decoration: none;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #0f766e;
  font-weight: 800;
}
.brand strong {
  display: block;
  font-size: 14px;
  line-height: 1.2;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 7px;
  color: var(--sidebar-text);
  font-weight: 500;
  text-decoration: none;
}
.nav-link svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
}
.nav-link:hover {
  background: var(--sidebar-active);
  text-decoration: none;
}
.nav-link.active {
  background: var(--sidebar-active);
  color: #fff;
  box-shadow: inset 2px 0 0 #2dd4bf;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: auto;
  padding: 0 8px;
}
.sidebar-footer .badge {
  align-self: flex-start;
}
.tracker-url {
  color: var(--sidebar-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.tracker-url code {
  color: var(--sidebar-text);
}

.main {
  min-width: 0;
  padding: 32px 40px 64px;
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .sidebar {
    position: static;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    height: auto;
    padding: 12px 16px;
  }
  .brand {
    padding: 0;
  }
  .nav {
    flex-direction: row;
  }
  .sidebar-footer {
    display: none;
  }
  .main {
    padding: 20px 16px 48px;
  }
}
</style>
