<template>
  <div class="tenondera-brand" :class="{ compact }">
    <svg class="tenondera-mark" viewBox="0 0 112 110" fill="none" role="img" aria-label="Símbolo Tenonderã: ojo y red de conexiones">
      <defs>
        <linearGradient id="tenondera-neon" x1="8" y1="92" x2="101" y2="17" gradientUnits="userSpaceOnUse">
          <stop stop-color="#2476d7"/><stop offset=".5" stop-color="#15d9e8"/><stop offset="1" stop-color="#34e4a0"/>
        </linearGradient>
      </defs>
      <g stroke="#061f49" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">
        <path d="M47 12 58 18 70 9 79 20 93 19 99 35 92 50 100 61 91 75 96 89 80 96 68 90 55 101 43 94 30 100 24 86 11 78 17 62 10 52 18 39 15 26 30 23Z"/>
      </g>
      <g stroke="url(#tenondera-neon)" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
        <path d="M58 18 55 101M15 52 100 61M30 23 80 96M93 19 24 86M47 12 68 90M11 78 92 50M18 39 91 75M17 62 79 20M30 100 99 35M43 94 70 9"/>
        <path d="M15 52 37 30 58 18 79 20 92 50 91 75 68 90 43 94 24 86 17 62Z"/>
        <path d="M20 56 40 40 57 33 75 41 90 57 74 70 56 80 38 69Z" stroke-width="2.7"/>
        <path d="M27 56Q56 24 85 56Q56 88 27 56Z" fill="#061f49" stroke-width="3"/>
        <circle cx="56" cy="56" r="17" fill="#16d5da" stroke="#061f49" stroke-width="2"/>
        <circle cx="58" cy="56" r="9" fill="#072b59" stroke="none"/>
        <circle cx="62" cy="51" r="3" fill="#effffb" stroke="none"/>
      </g>
      <g fill="#39e3bf" stroke="#08355d" stroke-width="1.5">
        <circle cx="58" cy="18" r="4"/><circle cx="15" cy="52" r="4"/><circle cx="100" cy="61" r="4"/>
        <circle cx="30" cy="23" r="3"/><circle cx="93" cy="19" r="3"/><circle cx="24" cy="86" r="3"/><circle cx="68" cy="90" r="3"/>
      </g>
      <path d="m76 22 28-15-9 32-5-12-14-5Z" fill="#051e47" stroke="#051e47" stroke-width="6" stroke-linejoin="round"/>
      <path d="m77 22 28-15-9 32-6-13-13-4Z" stroke="#18d6bd" stroke-width="2.8" stroke-linejoin="round"/>
      <path d="m89 26 16-19" stroke="#18d6bd" stroke-width="2.2"/>
    </svg>
    <div class="brand-words">
      <strong>TENONDERÃ</strong>
      <span>SIMULANDO EL FUTURO</span>
    </div>
  </div>
</template>
<script setup>
defineProps({ compact: { type: Boolean, default: false } })
</script>
<style scoped>
.tenondera-brand{display:inline-flex;align-items:center;gap:12px;color:#061b44;white-space:nowrap}
.tenondera-mark{width:72px;height:72px;filter:drop-shadow(0 5px 10px rgba(13,157,194,.13));flex-shrink:0}
.brand-words{display:flex;flex-direction:column;gap:3px}
.brand-words strong{font-family:Inter,'Segoe UI',sans-serif;font-size:29px;font-weight:900;letter-spacing:.055em;line-height:1}
.brand-words span{font-size:10px;font-weight:800;letter-spacing:.21em;color:#174274}
.compact .tenondera-mark{width:45px;height:45px}
.compact .brand-words strong{font-size:18px}
.compact .brand-words span{font-size:7px}
@media(max-width:650px){.tenondera-mark{width:55px;height:55px}.brand-words strong{font-size:20px}.brand-words span{font-size:8px}}
</style>
