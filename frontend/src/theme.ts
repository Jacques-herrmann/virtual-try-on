/**
 * Thème PrimeVue de Wearo (valeurs de `brand/tokens.json`).
 *
 * Les palettes d'Aura utilisées pour les états (green, orange, yellow, amber, red, sky, blue)
 * sont remplacées par celles de la marque : boutons, étiquettes, messages et notifications
 * suivent tous la DA sans réglage composant par composant.
 */
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

const apricot = {
  50: '#FEF5F0', 100: '#FDE8DC', 200: '#FACDB5', 300: '#F5AC86', 400: '#EF8D5D', 500: '#E8774A',
  600: '#D05E30', 700: '#AD4A24', 800: '#8A3C20', 900: '#6F331E', 950: '#3D180C',
}
/** Neutres chauds ; 900 = prune, la couleur du texte. */
const sand = {
  0: '#FFFFFF', 50: '#FBF7F2', 100: '#F4EDE5', 200: '#E9DFD4', 300: '#D8CBBE', 400: '#B5A595',
  500: '#8E7E70', 600: '#6E6058', 700: '#544843', 800: '#3D3331', 900: '#2E1F2B', 950: '#1E1520',
}
const sage = {
  50: '#F1F7F2', 100: '#E3EFE5', 200: '#C6DECB', 300: '#9FC6A8', 400: '#74A880', 500: '#548C62',
  600: '#42724F', 700: '#2F5D3B', 800: '#284B32', 900: '#213D2A', 950: '#102016',
}
const honey = {
  50: '#FEF8EC', 100: '#FDF0D5', 200: '#F9DFA8', 300: '#F3C872', 400: '#E9AE45', 500: '#D9932A',
  600: '#9A6516', 700: '#7A5410', 800: '#5F420F', 900: '#4A340E', 950: '#2A1C06',
}
const brick = {
  50: '#FDF3F1', 100: '#FBE3E0', 200: '#F5C6C0', 300: '#EC9E94', 400: '#DE7466', 500: '#C9564A',
  600: '#B4453A', 700: '#A33A2E', 800: '#84302A', 900: '#6C2A26', 950: '#3A1311',
}
const plum = {
  50: '#F7F3F9', 100: '#EDE6F2', 200: '#DACDE5', 300: '#BFA9D2', 400: '#9E80B8', 500: '#82659E',
  600: '#6C5287', 700: '#5B4370', 800: '#4A375B', 900: '#3D2E4A', 950: '#221829',
}

const scale = (name: string) =>
  Object.fromEntries(
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((n) => [n, `{${name}.${n}}`]),
  )

export const WearoTheme = definePreset(Aura, {
  primitive: {
    borderRadius: { none: '0', xs: '4px', sm: '8px', md: '12px', lg: '14px', xl: '18px' },
    apricot,
    sand,
    green: sage,
    emerald: sage,
    orange: honey,
    yellow: honey,
    amber: honey,
    red: brick,
    sky: plum,
    blue: plum,
  },
  semantic: {
    primary: scale('apricot'),
    focusRing: { width: '2px', style: 'solid', color: '{apricot.600}', offset: '2px', shadow: 'none' },
    formField: {
      paddingX: '0.875rem',
      paddingY: '0.625rem',
      borderRadius: '{border.radius.md}',
    },
    content: { borderRadius: '{border.radius.lg}' },
    overlay: {
      select: { shadow: '0 8px 24px rgba(46, 31, 43, 0.10)' },
      popover: { shadow: '0 8px 24px rgba(46, 31, 43, 0.10)' },
      modal: { shadow: '0 24px 48px rgba(46, 31, 43, 0.18)' },
    },
    colorScheme: {
      light: {
        surface: sand,
        // Texte prune sur abricot : 5,3:1 (le blanc ne donne que 2,9:1).
        primary: {
          color: '{apricot.500}',
          contrastColor: '{sand.900}',
          hoverColor: '{apricot.400}',
          activeColor: '{apricot.600}',
        },
        highlight: {
          background: '{apricot.50}',
          focusBackground: '{apricot.100}',
          color: '{apricot.800}',
          focusColor: '{apricot.900}',
        },
        mask: { background: 'rgba(46, 31, 43, 0.45)' },
        formField: {
          borderColor: '{sand.300}',
          hoverBorderColor: '{sand.400}',
          focusBorderColor: '{apricot.600}',
          color: '{sand.900}',
          placeholderColor: '{sand.500}',
          floatLabelFocusColor: '{apricot.700}',
          iconColor: '{sand.500}',
          shadow: 'none',
        },
        text: {
          color: '{sand.900}',
          hoverColor: '{sand.950}',
          mutedColor: '{sand.600}',
          hoverMutedColor: '{sand.700}',
        },
        content: { hoverBackground: '{sand.100}' },
      },
    },
  },
  components: {
    button: {
      root: { label: { fontWeight: '700' }, paddingX: '1.125rem' },
      colorScheme: {
        light: {
          root: {
            secondary: {
              background: '{sand.0}',
              hoverBackground: '{sand.100}',
              activeBackground: '{sand.200}',
              borderColor: '{sand.300}',
              hoverBorderColor: '{sand.400}',
              activeBorderColor: '{sand.400}',
              color: '{sand.900}',
              hoverColor: '{sand.900}',
              activeColor: '{sand.900}',
            },
          },
          outlined: { primary: { borderColor: '{apricot.300}', color: '{apricot.700}' } },
          text: { primary: { color: '{apricot.700}' }, secondary: { color: '{sand.700}' } },
          link: { color: '{apricot.700}', hoverColor: '{apricot.800}', activeColor: '{apricot.900}' },
        },
      },
    },
    card: {
      root: { borderRadius: '{border.radius.xl}', shadow: '0 2px 8px rgba(46, 31, 43, 0.05)' },
      body: { padding: '1.5rem', gap: '0.75rem' },
      title: { fontSize: '1.25rem', fontWeight: '800' },
    },
    tag: {
      root: { borderRadius: '999px', padding: '0.3rem 0.75rem', fontSize: '0.8125rem' },
    },
    message: {
      root: { borderRadius: '{border.radius.lg}' },
    },
    toast: {
      root: { borderRadius: '{border.radius.lg}' },
    },
    dialog: {
      title: { fontSize: '1.25rem', fontWeight: '800' },
    },
  },
})
