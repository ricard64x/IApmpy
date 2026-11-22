<template>
  <main class="password-layout">
    <section class="panel">
      <TenonderaBrand />
      <div class="eyebrow">PROTEGÉ TU CUENTA</div>
      <h1>Actualizá tu contraseña</h1>
      <p>Por seguridad, antes de usar Tenonderã tenés que reemplazar la contraseña temporal. Esta operación cerrará tu sesión.</p>
      <form @submit.prevent="submit">
        <label for="current">Contraseña actual</label>
        <input id="current" type="password" v-model="currentPassword" autocomplete="current-password" required/>
        <label for="next">Nueva contraseña (mínimo 12 caracteres)</label>
        <input id="next" type="password" v-model="newPassword" autocomplete="new-password" required minlength="12"/>
        <label for="repeat">Confirmar nueva contraseña</label>
        <input id="repeat" type="password" v-model="confirmPassword" autocomplete="new-password" required minlength="12"/>
        <div class="error" v-if="error" role="alert">{{error}}</div>
        <button :disabled="saving" type="submit">{{saving?'Guardando…':'Guardar nueva contraseña →'}}</button>
      </form>
    </section>
  </main>
</template>
<script setup>
import {ref} from 'vue'
import {useRouter} from 'vue-router'
import TenonderaBrand from '../components/TenonderaBrand.vue'
import {updateOwnPassword} from '../api/auth'
const router=useRouter()
const currentPassword=ref(''),newPassword=ref(''),confirmPassword=ref(''),saving=ref(false),error=ref('')
async function submit(){
 if(newPassword.value!==confirmPassword.value){error.value='Las contraseñas no coinciden.';return}
 saving.value=true;error.value=''
 try {await updateOwnPassword(currentPassword.value,newPassword.value);await router.replace('/login')}
 catch(e){error.value=e.message||'No se pudo actualizar.'}
 finally{saving.value=false}
}
</script>
<style scoped>
.password-layout{min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 20% 10%,#e1f9f7,#f4f8fe 40%,white);padding:22px;color:#0d2955;font-family:Inter,'Segoe UI',sans-serif}
.panel{background:white;border:1px solid #dbe7f1;box-shadow:0 25px 80px #173f7020;border-radius:24px;padding:clamp(28px,5vw,58px);max-width:530px;width:100%}
.eyebrow{margin-top:38px;color:#008f9a;letter-spacing:.17em;font-size:11px;font-weight:800}.panel h1{font-size:34px;line-height:1.1;letter-spacing:-.04em;margin:15px 0}.panel p{line-height:1.7;color:#597389;margin-bottom:24px}
form{display:grid;gap:12px}label{font-weight:650;font-size:13px}input{height:52px;border:1px solid #d5e2ea;border-radius:11px;padding:0 14px;font:inherit}input:focus{outline:3px solid #22dad526;border-color:#1dbab6}button{margin-top:14px;background:linear-gradient(95deg,#0c4189,#07b6aa);color:white;font-weight:750;border:0;border-radius:12px;height:54px;cursor:pointer}.error{padding:11px;border-radius:10px;background:#fff0f0;color:#b02c2c}
</style>
