import '@fontsource/plus-jakarta-sans/latin-400.css'
import '@fontsource/plus-jakarta-sans/latin-500.css'
import '@fontsource/plus-jakarta-sans/latin-600.css'
import '@fontsource/plus-jakarta-sans/latin-700.css'
import '@fontsource/plus-jakarta-sans/latin-800.css'
import './style.css'

import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import { createApp } from 'vue'

import App from './App.vue'
import { fr } from './locale'
import { router } from './router'
import { KaloeTheme } from './theme'

createApp(App)
  .use(PrimeVue, { theme: { preset: KaloeTheme, options: { darkModeSelector: false } }, locale: fr })
  .use(ToastService)
  .use(ConfirmationService)
  .use(router)
  .mount('#app')
