<template>
  <div class="ten-shell">
    <aside class="sidebar" :class="{ opened: menuOpened }">
      <div class="sidebar-logo"><TenonderaBrand compact /></div>
      <div class="profile-box"><div class="avatar">{{ (activeUser?.name||'U')[0]?.toUpperCase() }}</div><div><strong>{{ activeUser?.name }}</strong><span>{{ roleLabel }}</span></div></div>
      <nav class="side-nav" aria-label="Navegación principal">
        <RouterLink to="/" exact-active-class="selected" @click="menuOpened=false"><span>⌂</span> Inicio</RouterLink>
        <RouterLink to="/workspace" active-class="selected" @click="menuOpened=false"><span>◇</span> Nueva simulación</RouterLink>
        <RouterLink v-if="isAdmin" to="/administracion" active-class="selected" @click="menuOpened=false"><span>♧</span> Usuarios y perfiles</RouterLink>
        <RouterLink to="/" @click="menuOpened=false"><span>▣</span> Mis simulaciones</RouterLink>
      </nav>
      <div class="side-bottom"><div class="lace-mark">✺</div><div class="sidebar-flag"><span></span><span></span><span></span></div><small>Tenonderã · Paraguay 🇵🇾<br/>Simulando el futuro</small></div>
    </aside>
    <div v-if="menuOpened" class="scrim" @click="menuOpened=false"></div>
    <div class="page">
      <header class="toolbar">
        <button class="mobile-menu" @click="menuOpened=!menuOpened" aria-label="Menú">☰</button>
        <div><div class="breadcrumb">TENONDERÃ / {{ section }}</div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div>
        <div class="toolbar-right">
          <span class="flag-pill">🇵🇾 Paraguay</span>
          <div class="user-menu">
            <button class="user-button" @click="open=!open" :aria-expanded="open"><span class="top-avatar">{{(activeUser?.name||'U')[0]?.toUpperCase()}}</span>⌄</button>
            <div v-if="open" class="dropdown">
              <strong>{{activeUser?.username}}</strong>
              <span>{{roleLabel}}</span>
              <button @click="changePassword">Cambiar contraseña</button>
              <button @click="signOut">Cerrar sesión</button>
            </div>
          </div>
        </div>
      </header>
      <main class="page-content"><slot /></main>
    </div>
  </div>
</template>
<script setup>
import {computed,ref} from 'vue'
import {useRouter} from 'vue-router'
import TenonderaBrand from './TenonderaBrand.vue'
import {activeUser,logoutUser} from '../api/auth'
const props=defineProps({title:{type:String,default:'Panel de control'},subtitle:{type:String,default:'Gestioná tus simulaciones y recursos.'},section:{type:String,default:'INICIO'}})
const open=ref(false),menuOpened=ref(false),router=useRouter()
const isAdmin=computed(()=>activeUser.value?.role==='administrator')
const roleLabel=computed(()=>({administrator:'Administrador',analyst:'Analista',researcher:'Investigador'}[activeUser.value?.role]||'Usuario'))
const signOut=async()=>{try{await logoutUser()}finally{router.replace('/login')}}
const changePassword=()=>{open.value=false;router.push('/cambiar-clave')}
</script>
<style scoped>
.ten-shell{display:flex;min-height:100vh;background:#f5f8fd;color:#102b52;font-family:Inter,'Segoe UI',sans-serif}
.sidebar{position:sticky;top:0;display:flex;flex-direction:column;width:255px;min-width:255px;max-height:100vh;background:linear-gradient(170deg,#082952 0%,#061c41 55%,#035274 100%);color:#fff;padding:25px 15px;overflow:auto;z-index:50}
.sidebar-logo{padding:10px 5px 29px;border-bottom:1px solid #86b6e12a}
.sidebar-logo :deep(.brand-words strong){color:white}.sidebar-logo :deep(.brand-words span){color:#b5e6ee}
.profile-box{display:flex;gap:12px;align-items:center;padding:24px 10px;color:#f5faff}.avatar,.top-avatar{width:40px;height:40px;display:grid;place-items:center;border-radius:50%;background:#fff1;color:#d7fdff;border:1px solid #ffffff55;font-weight:800}.profile-box strong{display:block;font-size:13px}.profile-box span{font-size:11px;color:#aad8ed}.side-nav{display:grid;gap:6px;margin-top:12px}.side-nav a{text-decoration:none;display:flex;align-items:center;gap:14px;border-radius:11px;color:#d4e4f4;font-size:13px;padding:13px 15px;font-weight:650;transition:background .2s}.side-nav a span{font-size:23px;width:25px;text-align:center}.side-nav a:hover,.side-nav a.selected{background:linear-gradient(90deg,#0078b3,#0ac2be);color:#fff;box-shadow:0 6px 12px #001b3833}
.side-bottom{position:relative;margin-top:auto;padding:20px 14px;overflow:hidden;border-top:1px solid #86b6e12a;min-height:140px}.side-bottom small{display:block;color:#a8cde0;line-height:1.8;position:relative;font-size:10px}.lace-mark{position:absolute;font-size:150px;color:#e4fbfa12;right:-26px;bottom:-51px;line-height:1}.sidebar-flag{display:flex;width:78px;height:4px;margin-bottom:15px}.sidebar-flag span{flex:1;background:#db354b}.sidebar-flag span:nth-child(2){background:white}.sidebar-flag span:last-child{background:#2c72d9}
.page{flex:1;min-width:0}.toolbar{min-height:126px;display:flex;justify-content:space-between;align-items:center;padding:28px clamp(22px,3.5vw,56px);gap:20px;background:#fff;border-bottom:1px solid #e5edf5}.breadcrumb{font-size:10px;font-weight:750;color:#048b9d;letter-spacing:.19em;margin-bottom:9px}.toolbar h1{margin:0;font-size:clamp(22px,2.3vw,32px);letter-spacing:-.04em;line-height:1.1}.toolbar p{margin:9px 0 0;font-size:13px;color:#68849b}.toolbar-right{display:flex;align-items:center;gap:25px}.flag-pill{border:1px solid #e2ebf1;padding:8px 13px;border-radius:100px;color:#3b5f7b;font-size:12px;white-space:nowrap}.user-menu{position:relative}.user-button{border:0;background:#f2f6fb;display:flex;align-items:center;gap:10px;border-radius:100px;padding:5px 12px 5px 5px;cursor:pointer}.top-avatar{background:linear-gradient(110deg,#0972ca,#11b5b3);color:#fff;border:0;width:35px;height:35px}.dropdown{position:absolute;right:0;top:50px;width:215px;z-index:30;background:white;border:1px solid #e1edf3;border-radius:14px;box-shadow:0 18px 44px #13365325;padding:13px}.dropdown strong{font-size:13px;display:block}.dropdown span{font-size:11px;color:#678197}.dropdown button{width:100%;text-align:left;background:none;border:0;padding:11px 6px;font-size:13px;color:#254b69;cursor:pointer}.dropdown button:hover{background:#f1f8fb}.page-content{max-width:1550px;margin:0 auto;padding:clamp(18px,3vw,44px)}.mobile-menu{display:none}.scrim{display:none}
@media(max-width:900px){.sidebar{position:fixed;left:0;height:100vh;transform:translateX(-110%);transition:transform .2s}.sidebar.opened{transform:translateX(0)}.scrim{display:block;position:fixed;inset:0;background:#0a1b426b;z-index:45}.mobile-menu{display:block;border:0;background:#eff6f9;padding:12px;border-radius:9px;font-size:20px}.flag-pill{display:none}.toolbar{min-height:100px}.toolbar p{font-size:11px}}
</style>
