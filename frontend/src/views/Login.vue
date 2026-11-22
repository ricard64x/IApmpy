<template>
  <main class="login-layout">
    <section class="scene" aria-label="Identidad paraguaya">
      <div class="tricolor"><span></span><span></span><span></span></div>
      <div class="mandala mandala-one">✺</div><div class="mandala mandala-two">✺</div>
      <div class="scene-text">
        <div class="eyebrow">✦ DESARROLLADO PARA MIRAR MÁS ALLÁ</div>
        <h1>Simulando<br><em>el futuro.</em></h1>
        <p>Explorá escenarios, descubrí tendencias y anticipá decisiones con inteligencia colectiva.</p>
        <div class="scene-features"><span>◈ Simulación social</span><span>◇ Análisis prospectivo</span><span>↗ Visión de futuro</span></div>
      </div>
      <svg class="skyline" viewBox="0 0 680 210" aria-hidden="true">
        <path d="M0 206V147h35v-18h30v24h26V94h23v-17h8V58h11v19h8v17h20v59h29v-40h24v-19h11v19h19v40h25v-28h30v-19h18v19h18v28h38V75h30v-15h11V34h14v26h10v15h31v78h36v-42h44v42h30v-28h47v28h41v-53h35v53h32v-25h52v25h30v53Z" fill="#16477a" opacity=".55"/>
        <path d="M0 190Q170 160 320 188T680 179V210H0Z" fill="#0b315e" opacity=".8"/>
        <g fill="#56c9da"><circle cx="125" cy="119" r="2"/><circle cx="335" cy="101" r="3"/><circle cx="455" cy="130" r="2"/></g>
      </svg>
      <div class="scene-footer">PARAGUAY <span class="flag">🇵🇾</span> • TENONDERÃ</div>
    </section>

    <section class="form-side">
      <header class="form-top"><TenonderaBrand /><span class="secure-note">● ACCESO SEGURO</span></header>
      <div class="login-card">
        <div class="welcome-badge">BIENVENIDO A TU FUTURO</div>
        <h2>Iniciá sesión</h2>
        <p>Ingresá a tu espacio privado de simulaciones.</p>
        <form @submit.prevent="submit" autocomplete="on">
          <label for="login-user">Usuario o correo electrónico</label>
          <div class="field"><span>✉</span><input id="login-user" v-model.trim="username" autocomplete="username" autofocus required placeholder="Tu usuario" /></div>
          <label for="login-password">Contraseña</label>
          <div class="field"><span>♧</span><input id="login-password" v-model="password" :type="showPassword ? 'text':'password'" autocomplete="current-password" required placeholder="Ingresá tu contraseña" /><button class="eye" type="button" @click="showPassword=!showPassword" :aria-label="showPassword?'Ocultar contraseña':'Mostrar contraseña'">{{ showPassword ? '◉' : '◎' }}</button></div>
          <p v-if="error" role="alert" class="form-error">{{ error }}</p>
          <button class="primary-button" :disabled="loading || !username || !password" type="submit">
            {{ loading?'Verificando acceso…':'Iniciar sesión' }} <span>→</span>
          </button>
        </form>
        <div class="reset-hint">¿Olvidaste la contraseña? Solicitá el restablecimiento al administrador.</div>
        <div class="admin-note">◈ Las cuentas son creadas y autorizadas únicamente por el administrador.</div>
      </div>
      <footer class="form-footer"><span>© 2026 TENONDERÃ · Simulando el futuro</span><span class="flag-lines"></span></footer>
    </section>
  </main>
</template>
<script setup>
import {ref} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import TenonderaBrand from '../components/TenonderaBrand.vue'
import {loginUser} from '../api/auth'
const route=useRoute(),router=useRouter()
const username=ref(''),password=ref(''),showPassword=ref(false),loading=ref(false),error=ref('')
const submit=async()=>{
  loading.value=true;error.value=''
  try {
    const user=await loginUser(username.value,password.value)
    await router.replace(user.must_change_password ? '/cambiar-clave' : (typeof route.query.redirect==='string' && route.query.redirect.startsWith('/') && !route.query.redirect.startsWith('//') ? route.query.redirect : '/'))
  }catch(e){error.value=e.message||'No se pudo iniciar sesión.'}
  finally{loading.value=false;password.value=''}
}
</script>
<style scoped>
.login-layout{min-height:100vh;display:grid;grid-template-columns:minmax(340px,43%) 1fr;background:#fff;color:#0b2149;font-family:Inter,'Segoe UI',sans-serif}
.scene{min-height:100vh;position:relative;overflow:hidden;color:white;background:linear-gradient(158deg,#083b76 4%,#06214c 47%,#006a8e 100%);display:flex;flex-direction:column;justify-content:center;padding:65px clamp(32px,6vw,98px)}
.scene:before{content:"";position:absolute;inset:0;background-image:radial-gradient(circle at 15% 25%,#33f1d541 0 1px,transparent 2px),radial-gradient(circle at 75% 75%,#88eaf022 0 1px,transparent 2px);background-size:45px 45px;pointer-events:none}
.scene:after{content:"";position:absolute;left:-25%;bottom:-30%;width:95%;aspect-ratio:1;border:1px solid #2fc9d72c;border-radius:50%;box-shadow:0 0 0 55px #34e5db0b,0 0 0 110px #34e5db0a,0 0 0 165px #34e5db08}
.tricolor{position:absolute;left:0;top:0;width:100%;height:7px;display:flex}.tricolor span{flex:1;background:#df2635}.tricolor span:nth-child(2){background:#fff}.tricolor span:nth-child(3){background:#2668c9}
.scene-text{position:relative;z-index:1}.eyebrow{font-size:12px;letter-spacing:.19em;color:#67e7e3;font-weight:700}.scene h1{font-size:clamp(49px,5vw,85px);line-height:1.09;letter-spacing:-.055em;margin:28px 0}.scene em{color:#61e9e1;font-weight:500}.scene p{max-width:450px;color:#dcebf5;font-size:18px;line-height:1.75}.scene-features{display:flex;gap:14px;flex-wrap:wrap;margin-top:35px;color:#bdfdf7;font-size:12px}.scene-features span{padding:10px 14px;border:1px solid #a2fffd52;border-radius:100px;background:#c5f8ff0a}.mandala{position:absolute;color:#a6f2f22d;font-size:320px;line-height:1;top:-120px;right:-65px;transform:rotate(24deg);font-family:serif}.mandala-two{left:-150px;top:auto;bottom:40px;font-size:270px;opacity:.5}.skyline{position:absolute;bottom:50px;left:0;width:100%;z-index:0}.scene-footer{position:absolute;bottom:27px;left:clamp(32px,6vw,98px);letter-spacing:.16em;font-size:11px;color:#b1dfee;z-index:2}.flag{font-size:16px}
.form-side{min-height:100vh;display:flex;flex-direction:column;padding:44px clamp(34px,6vw,98px);position:relative;overflow:hidden;background-image:radial-gradient(circle at 100% 100%,#ddf6f5 0,transparent 43%)}
.form-side:after{content:"";position:absolute;right:-50px;bottom:-140px;width:350px;height:350px;border-radius:50%;border:1px solid #2baed71d;box-shadow:0 0 0 50px #18bbd608,0 0 0 100px #18bbd608;pointer-events:none}
.form-top,.form-footer{display:flex;align-items:center;justify-content:space-between;gap:15px;position:relative;z-index:1}.secure-note{color:#008c93;font-size:10px;font-weight:800;letter-spacing:.11em}.login-card{margin:auto;width:min(100%,430px);padding:35px 0;position:relative;z-index:1}.welcome-badge{font-size:11px;letter-spacing:.17em;color:#008eac;font-weight:800;margin-bottom:17px}.login-card h2{font-size:clamp(32px,3vw,44px);letter-spacing:-.048em;margin:0 0 11px;font-weight:800}.login-card>p{color:#66809b;font-size:15px;margin-bottom:36px}.login-card form{display:grid;gap:11px}.login-card label{font-size:13px;color:#163c5d;font-weight:700;margin-top:8px}.field{border:1px solid #d8e4ec;background:#fff;border-radius:12px;height:55px;display:flex;align-items:center;gap:11px;padding:0 15px;transition:.2s;box-shadow:0 6px 18px #07375d06}.field:focus-within{border-color:#00b8be;box-shadow:0 0 0 4px #0dc4bd16}.field>span{color:#0083a6;font-size:20px}.field input{width:100%;border:none;outline:none;background:transparent;font:inherit;color:#0b2149;font-size:14px}.eye{border:none;background:none;cursor:pointer;color:#648299;font-size:20px}.primary-button{border:0;height:56px;color:#fff;background:linear-gradient(96deg,#0c438c,#00b7a9);border-radius:12px;margin-top:17px;font-size:15px;font-weight:750;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:15px;box-shadow:0 14px 26px #004a8d2b}.primary-button:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 17px 30px #004a8d30}.primary-button:disabled{opacity:.6;cursor:default}.form-error{border-radius:9px;background:#ffecec;color:#a52c34;padding:12px;font-size:13px}.reset-hint{font-size:12px;text-align:center;color:#4e6988;margin-top:24px;line-height:1.6}.admin-note{margin-top:32px;padding:16px;border-radius:12px;background:#eef9fc;color:#417383;font-size:12px;line-height:1.7}.form-footer{font-size:11px;color:#7c90a8}.flag-lines{width:100px;height:5px;background:linear-gradient(to right,#e73745 0 33%,white 33% 66%,#256ac5 66%)}
@media(max-width:970px){.login-layout{grid-template-columns:1fr}.scene{min-height:280px;padding:40px}.scene h1{font-size:52px;margin:14px 0}.scene p{font-size:14px}.scene-features,.mandala,.scene-footer,.skyline{display:none}.form-side{min-height:660px;padding:28px 28px 32px}.secure-note{display:none}}
@media(max-width:540px){.scene{min-height:215px}.scene h1{font-size:40px}.scene p{display:none}.login-card{padding:34px 0}}
</style>
