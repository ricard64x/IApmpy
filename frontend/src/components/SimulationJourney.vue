<template>
  <section class="journey" :class="{dark:theme==='dark',compact}" aria-label="Pasos de la simulación">
    <div class="journey-top" v-if="!compact">
      <div>
        <span class="eyebrow">GUÍA DE PRINCIPIO A FIN</span>
        <h2>De una pregunta a un resultado que podés explorar</h2>
        <p>El recorrido tiene cinco pasos. Podés volver a tus proyectos sin perder las versiones guardadas.</p>
      </div>
      <span class="step-summary" v-if="currentStep">Paso {{ currentStep }} de 5</span>
    </div>
    <ol class="journey-track">
      <li v-for="step in JOURNEY_STEPS" :key="step.number"
          :class="{current:currentStep===step.number,done:currentStep>step.number}">
        <span class="step-index" aria-hidden="true">{{ currentStep>step.number ? '✓' : step.number }}</span>
        <div>
          <strong>{{ step.title }}</strong>
          <small>{{compact?step.short:step.description}}</small>
        </div>
      </li>
    </ol>
    <p class="journey-foot" v-if="!compact">Las conversaciones y decisiones representan un escenario posible, no respuestas de personas reales.</p>
  </section>
</template>
<script setup>
import {JOURNEY_STEPS} from '../utils/dashboardJourney'
defineProps({
  currentStep:{type:Number,default:0},
  theme:{type:String,default:'light'},
  compact:{type:Boolean,default:false},
})
</script>
<style scoped>
.journey{background:#fff;border:1px solid #dfeaf1;border-radius:20px;padding:clamp(17px,2.1vw,27px);box-shadow:0 5px 24px #102e4a09;min-width:0}
.journey-top{display:flex;gap:18px;align-items:flex-start;justify-content:space-between;margin-bottom:21px}
.eyebrow{color:#037e9e;letter-spacing:.14em;font-size:10px;font-weight:800}
.journey h2{margin:7px 0 6px;font-size:clamp(18px,2vw,23px);letter-spacing:-.025em;line-height:1.25;color:#173953}
.journey p{margin:0;line-height:1.6;color:#637e91;font-size:12px}
.step-summary{white-space:nowrap;border:1px solid #b9dce6;border-radius:999px;padding:8px 13px;color:#145774;background:#eaf8fa;font-weight:800;font-size:11px}
.journey-track{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.journey-track li{min-width:0;display:flex;gap:10px;align-items:flex-start;padding:12px;border:1px solid #e1edf2;background:#f8fbfd;border-radius:13px}
.step-index{display:grid;place-items:center;flex:none;width:30px;height:30px;border-radius:9px;background:#e5eff5;color:#276381;font-size:13px;font-weight:800}
.journey-track strong{display:block;font-size:12px;line-height:1.4;color:#264960}
.journey-track small{display:block;margin-top:5px;font-size:11px;color:#6f899c;line-height:1.5}
.journey-track li.current{border-color:#66bbcd;background:#edf9fc}
.journey-track li.current .step-index{background:#0c789b;color:white}
.journey-track li.done .step-index{background:#def6ea;color:#0a8557}
.journey-foot{margin-top:14px!important;font-size:11px!important}
.journey.dark{background:transparent;border-color:#ffffff3b;box-shadow:none;color:white}
.journey.dark .eyebrow{color:#6ee2d7}
.journey.dark .journey-track li{background:#ffffff12;border-color:#ffffff2a}
.journey.dark .journey-track strong,.journey.dark h2{color:#fff}
.journey.dark .journey-track small,.journey.dark p{color:#c4dce6}
.journey.dark .step-index{background:#ffffff20;color:#85ffec}
.journey.dark .journey-track li.current{border-color:#56c9c3;background:#ffffff20}
.journey.dark .journey-track li.done .step-index{background:#16465c}
.journey.dark .step-summary{background:#ffffff13;color:white;border-color:#ffffff35}
.journey.compact{padding:12px;border:0;background:transparent;box-shadow:none}
.journey.compact .journey-track li{padding:9px}
.journey.compact .journey-track small{font-size:10px}
@media(max-width:1200px){.journey-track{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:720px){
 .journey-top{display:block}
 .step-summary{display:inline-block;margin-top:12px}
 .journey-track{grid-template-columns:1fr;gap:8px}
 .journey-track li{align-items:center;min-height:51px}
 .journey-track small{margin-top:2px}
 .journey{padding:16px}
}
</style>
