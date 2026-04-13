import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

/**
 * 根据依赖路径拆分前端构建产物，降低单个 chunk 体积。
 *
 * @param {string} id 当前被打包模块的绝对路径。
 * @returns {string | undefined} 命中的分包名称；未命中时返回 `undefined`。
 */
function createManualChunks(id) {
  if (!id.includes('node_modules')) {
    return undefined
  }

  if (id.includes('element-plus') || id.includes('@element-plus')) {
    return 'vendor-element-plus'
  }

  if (id.includes('vue-router') || id.includes('pinia') || id.includes('/vue/')) {
    return 'vendor-vue'
  }

  return 'vendor-misc'
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: createManualChunks,
      },
    },
  },
})
