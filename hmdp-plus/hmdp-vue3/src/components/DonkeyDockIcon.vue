<script setup>
defineProps({ decorative: Boolean })
</script>

<template>
  <svg
    viewBox="0 0 96 110"
    xmlns="http://www.w3.org/2000/svg"
    :aria-hidden="decorative ? 'true' : undefined"
    :role="decorative ? undefined : 'img'"
    :aria-label="decorative ? undefined : '驴友卡通小驴'"
    class="donkey-dock-icon"
  >
    <g
      stroke="#484943"
      stroke-width="2.4"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M64 69c11-6 21-2 21 8v12c0 5-4 8-10 7L64 92Z" fill="#a6b39a" />
      <path d="M74 74v15M77 78h7" fill="none" stroke="#79886f" />
      <path d="M29 72c-4 8-4 17 1 26h35c5-13 3-21-2-27Z" fill="#b9b7b0" />
      <path
        d="M34 94v10M58 94v10"
        fill="none"
        stroke-width="11"
        stroke="#a7a59e"
      />
      <path d="M28 105h12M53 105h12" fill="none" stroke-width="7" />
      <path
        d="M28 79c-8 2-11-4-12-10"
        fill="none"
        stroke="#b9b7b0"
        stroke-width="10"
      />
      <path d="m12 66 1-6c1-4 6-4 8-1l1 7c0 6-8 7-10 0Z" fill="#656760" />
      <path d="M29 42C14 24 13 5 21 5c10 0 19 18 21 34" fill="#aaa8a1" />
      <path d="M55 40C59 19 71 2 78 6c8 5-1 27-12 40" fill="#aaa8a1" />
      <path
        d="M25 33C20 23 19 13 22 13c4 0 10 12 12 20"
        fill="#e5beb4"
        stroke="none"
      />
      <path
        d="M64 33c3-10 9-21 12-20 3 2-3 15-8 22"
        fill="#e5beb4"
        stroke="none"
      />
      <path
        d="M19 54c0-17 12-27 29-27s30 10 30 27c0 18-12 30-30 30S19 72 19 54Z"
        fill="#bbb9b2"
      />
      <path
        d="m34 31 4-8 5 5 5-9 5 8 7-3 1 10"
        fill="#656760"
        stroke="#656760"
      />
      <ellipse cx="35" cy="51" rx="5" ry="6.8" fill="#33372f" stroke="none" />
      <ellipse cx="61" cy="51" rx="5" ry="6.8" fill="#33372f" stroke="none" />
      <circle cx="36.5" cy="49" r="1.9" fill="white" stroke="none" />
      <circle cx="62.5" cy="49" r="1.9" fill="white" stroke="none" />
      <path d="M29 40q5-3 10 0M56 40q5-3 10 0" fill="none" stroke-width="2" />
      <ellipse cx="28" cy="62" rx="6" ry="3" fill="#dfb6a7" stroke="none" />
      <ellipse cx="69" cy="62" rx="6" ry="3" fill="#dfb6a7" stroke="none" />
      <ellipse cx="48" cy="68" rx="22" ry="14" fill="#f1e7d4" />
      <ellipse cx="39" cy="65" rx="2.2" ry="3" fill="#777469" stroke="none" />
      <ellipse cx="57" cy="65" rx="2.2" ry="3" fill="#777469" stroke="none" />
      <path d="M40 73q8 7 16 0" fill="none" stroke-width="2" />
      <path d="m33 81 15 6 14-6-5 10-9-1-9 1Z" fill="#91a17c" />
      <path d="m48 89 8 3-3 9-7-10" fill="#91a17c" />
    </g>
  </svg>
</template>

<style scoped>
.donkey-dock-icon {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}
</style>
