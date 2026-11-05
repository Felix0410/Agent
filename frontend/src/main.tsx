import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

// 前端只负责展示当前已实现的功能；后端请求统一在 api.ts 处理。
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
