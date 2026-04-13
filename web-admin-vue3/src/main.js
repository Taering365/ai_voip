import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/global.scss'
import 'element-plus/dist/index.css'

/**
 * 注册应用依赖并挂载前端应用。
 *
 * 该函数负责初始化 Vue 应用、状态管理、路由以及 Element Plus，
 * 同时统一注册图标组件，便于页面直接使用。
 *
 * @returns {void}
 */
function bootstrapApplication() {
  const app = createApp(App)
  const pinia = createPinia()

  Object.entries(ElementPlusIconsVue).forEach(([iconName, component]) => {
    app.component(iconName, component)
  })

  app.use(pinia)
  app.use(router)
  app.use(ElementPlus)
  app.mount('#app')
}

bootstrapApplication()
