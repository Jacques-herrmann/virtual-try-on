import 'primeicons/primeicons.css'
import './style.css'

import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import { createApp } from 'vue'

import App from './App.vue'
import { fr } from './locale'
import { router } from './router'

const Theme = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{teal.50}',
      100: '{teal.100}',
      200: '{teal.200}',
      300: '{teal.300}',
      400: '{teal.400}',
      500: '{teal.500}',
      600: '{teal.600}',
      700: '{teal.700}',
      800: '{teal.800}',
      900: '{teal.900}',
      950: '{teal.950}',
    },
  },
})

createApp(App)
  .use(PrimeVue, { theme: { preset: Theme, options: { darkModeSelector: false } }, locale: fr })
  .use(ToastService)
  .use(ConfirmationService)
  .use(router)
  .mount('#app')
