// Design tokens do SUS Digital — extraídos das telas de referência (referencias/*.html).
// Arquivo CommonJS para ser usado tanto pelo tailwind.config.js quanto pelo código TS.

const colors = {
  'inverse-surface': '#263143',
  background: '#f9f9ff',
  'on-surface-variant': '#434750',
  'on-secondary-container': '#007238',
  'on-tertiary-container': '#f38b23',
  'on-secondary': '#ffffff',
  'on-background': '#111c2d',
  error: '#ba1a1a',
  'on-error': '#ffffff',
  'secondary-container': '#89f6a6',
  'inverse-primary': '#a7c8ff',
  'on-surface': '#111c2d',
  'on-secondary-fixed-variant': '#005227',
  'primary-fixed': '#d5e3ff',
  surface: '#f9f9ff',
  'on-tertiary-fixed-variant': '#6e3900',
  'surface-container-highest': '#d8e3fb',
  'surface-bright': '#f9f9ff',
  'surface-dim': '#cfdaf2',
  secondary: '#006d36',
  'surface-container-high': '#dee8ff',
  primary: '#00254d',
  'on-primary-container': '#7fa7e5',
  'surface-container': '#e7eeff',
  'secondary-fixed-dim': '#70dc8f',
  'inverse-on-surface': '#ecf1ff',
  'on-tertiary-fixed': '#2f1500',
  'on-error-container': '#93000a',
  tertiary: '#3d1d00',
  outline: '#737781',
  'on-secondary-fixed': '#00210c',
  'surface-container-low': '#f0f3ff',
  'primary-container': '#003b73',
  'on-primary': '#ffffff',
  'secondary-fixed': '#8cf9a9',
  'surface-variant': '#d8e3fb',
  'surface-tint': '#345f99',
  'on-tertiary': '#ffffff',
  'error-container': '#ffdad6',
  'tertiary-fixed': '#ffdcc3',
  'surface-container-lowest': '#ffffff',
  'on-primary-fixed-variant': '#174780',
  'on-primary-fixed': '#001c3b',
  'primary-fixed-dim': '#a7c8ff',
  'outline-variant': '#c3c6d1',
  'tertiary-container': '#5d2f00',
  'tertiary-fixed-dim': '#ffb77d',
  // fundo geral das telas nos HTMLs (rgb(248, 250, 252))
  canvas: '#f8fafc',
  // azul das bordas/filigranas decorativas
  accent: '#005baa',
};

// Escala tipográfica em px (os HTMLs usam rem; 1rem = 16px).
const fontSize = {
  'label-sm': [11, { lineHeight: '14px', letterSpacing: '0.9px' }],
  'label-md': [12, { lineHeight: '16px', letterSpacing: '0.7px' }],
  'label-lg': [14, { lineHeight: '20px', letterSpacing: '0.3px' }],
  'body-sm': [14, { lineHeight: '22px' }],
  'body-md': [16, { lineHeight: '25.6px' }],
  'body-lg': [18, { lineHeight: '28px' }],
  'title-md': [18, { lineHeight: '24px' }],
  'title-lg': [20, { lineHeight: '28px', letterSpacing: '-0.2px' }],
  'headline-sm': [22, { lineHeight: '28px' }],
  'headline-md': [30, { lineHeight: '38px' }],
  'headline-lg-mobile': [28, { lineHeight: '36px', letterSpacing: '-0.3px' }],
  'display-lg-mobile': [36, { lineHeight: '44px', letterSpacing: '-0.4px' }],
};

// No React Native cada peso de fonte é uma família separada.
const fontFamily = {
  sans: ['PlusJakartaSans_400Regular'],
  'sans-medium': ['PlusJakartaSans_500Medium'],
  'sans-semibold': ['PlusJakartaSans_600SemiBold'],
  'sans-bold': ['PlusJakartaSans_700Bold'],
  serif: ['Newsreader_400Regular'],
  'serif-medium': ['Newsreader_500Medium'],
  'serif-semibold': ['Newsreader_600SemiBold'],
};

module.exports = { colors, fontSize, fontFamily };
