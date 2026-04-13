import { defineStore } from 'pinia'

import {
  clearAccessToken,
  getAccessToken,
  getStoredUserInfo,
  setAccessToken,
  setStoredUserInfo,
} from '@/api/client'
import { fetchCurrentUserApi, loginApi } from '@/api/modules'
import { appMenus } from '@/utils/menu'

const ADMIN_ROLE_CODES = ['super_admin', 'ops_admin', 'enterprise_admin']

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getAccessToken(),
    userInfo: getStoredUserInfo(),
  }),
  getters: {
    /**
     * 判断当前用户是否已登录。
     *
     * @param {{ accessToken: string }} state Pinia 状态对象。
     * @returns {boolean} 访问令牌存在时返回 `true`。
     */
    isAuthenticated(state) {
      return Boolean(state.accessToken)
    },
    /**
     * 判断当前登录用户是否属于管理员。
     *
     * @param {{ userInfo: object | null }} state Pinia 状态对象。
     * @returns {boolean} 当前用户拥有管理员角色时返回 `true`。
     */
    isAdmin(state) {
      const roleCodes = state.userInfo?.role_codes || []
      return roleCodes.some((roleCode) => ADMIN_ROLE_CODES.includes(roleCode))
    },
    /**
     * 返回当前用户允许访问的菜单集合。
     *
     * @param {{ userInfo: object | null }} state Pinia 状态对象。
     * @returns {Array<object>} 已过滤后的菜单数组。
     */
    availableMenus(state) {
      const roleCodes = state.userInfo?.role_codes || []
      const isAdminUser = roleCodes.some((roleCode) => ADMIN_ROLE_CODES.includes(roleCode))
      return appMenus.filter((menuItem) => {
        if (menuItem.scope === 'both') {
          return true
        }
        if (menuItem.scope === 'admin') {
          return isAdminUser
        }
        return !isAdminUser
      })
    },
  },
  actions: {
    /**
     * 执行登录流程并缓存令牌与用户信息。
     *
     * @param {{username: string, password: string, captcha_key: string, captcha_code: string}} payload 登录表单数据。
     * @returns {Promise<object>} 登录后的用户信息对象。
     */
    async login(payload) {
      const result = await loginApi(payload)
      this.accessToken = result.access_token
      this.userInfo = result.user
      setAccessToken(result.access_token)
      setStoredUserInfo(result.user)
      return result.user
    },

    /**
     * 重新从后端同步当前登录用户信息。
     *
     * @returns {Promise<object | null>} 同步后的用户对象。
     */
    async refreshUser() {
      if (!this.accessToken) {
        return null
      }

      const user = await fetchCurrentUserApi()
      this.userInfo = user
      setStoredUserInfo(user)
      return user
    },

    /**
     * 清理前端缓存中的登录状态。
     *
     * @returns {void}
     */
    logout() {
      this.accessToken = ''
      this.userInfo = null
      clearAccessToken()
    },
  },
})
