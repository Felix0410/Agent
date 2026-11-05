import { defineConfig } from 'vite';
export default defineConfig({server:{host:'127.0.0.1',port:5173,strictPort:true,proxy:{'/health':'http://127.0.0.1:8000','/api':'http://127.0.0.1:8000'}}});
