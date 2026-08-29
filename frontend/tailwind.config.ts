import type {Config} from 'tailwindcss';
export default {content:['./app/**/*.{ts,tsx}','./components/**/*.{ts,tsx}'],theme:{extend:{colors:{paper:{50:'#fafafa',100:'#f5f5f4',200:'#e7e5e4'},ink:{600:'#57534e',900:'#1c1917'},accent:'#0f766e',status:{neutral:'#78716c'}}}},plugins:[]} satisfies Config;
