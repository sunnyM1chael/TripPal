<script setup>
import mascot from '@/assets/mascot/lvyou.png'

defineProps({ decorative: Boolean })
</script>

<template>
  <img
    class="donkey-mascot"
    :src="mascot"
    :alt="decorative ? '' : '驴友，背着绿色背包的小驴旅行伙伴'"
    width="384"
    height="454"
    decoding="async"
    draggable="false"
  />
</template>

<style scoped>
.donkey-mascot {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
}
</style>
