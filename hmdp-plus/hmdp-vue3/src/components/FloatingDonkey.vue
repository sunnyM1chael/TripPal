<script setup>
import { useRoute } from 'vue-router'
import DonkeyDockIcon from '@/components/DonkeyDockIcon.vue'

const route = useRoute()
</script>

<template>
  <router-link
    to="/travel"
    class="donkey-dock"
    :class="{ selected: route.path === '/travel' }"
    aria-label="打开驴友旅行助手"
    :aria-current="route.path === '/travel' ? 'page' : undefined"
  >
    <span class="figure"><DonkeyDockIcon decorative /></span>
    <span class="caption">驴友</span>
  </router-link>
</template>

<style scoped>
.donkey-dock {
  position: absolute;
  left: max(7px, env(safe-area-inset-left));
  bottom: calc(5px + env(safe-area-inset-bottom));
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 58px;
  color: #70746b;
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
}
.figure {
  display: block;
  width: 55px;
  height: 64px;
  transform-origin: 50% 100%;
  transition: transform 160ms ease;
}
.caption {
  font-size: 11px;
  line-height: 16px;
  font-weight: 500;
  margin-top: 1px;
}
.donkey-dock.selected {
  color: #292c28;
}
.donkey-dock.selected .caption {
  font-weight: 700;
}
.donkey-dock:hover .figure {
  transform: rotate(-4deg);
}
.donkey-dock:focus-visible {
  outline: 2px solid #43473e;
  outline-offset: 3px;
  border-radius: 12px;
}
@media (prefers-reduced-motion: reduce) {
  .figure {
    transition: none;
  }
  .donkey-dock:hover .figure {
    transform: none;
  }
}
</style>
