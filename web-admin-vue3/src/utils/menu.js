import homeIcon from '@/assets/icons/home.png'
import homeIconActive from '@/assets/icons/home_select.png'
import seatsIcon from '@/assets/icons/seats.png'
import seatsIconActive from '@/assets/icons/seats_select.png'
import tapeIcon from '@/assets/icons/tape.png'
import tapeIconActive from '@/assets/icons/tape_select.png'
import recordIcon from '@/assets/icons/record.png'
import recordIconActive from '@/assets/icons/record_select.png'
import expenseIcon from '@/assets/icons/expense.png'
import expenseIconActive from '@/assets/icons/expense_select.png'
import switchIcon from '@/assets/icons/switch.png'
import switchIconActive from '@/assets/icons/switch_select.png'

export const appMenus = [
  {
    path: '/dashboard',
    label: '控制台',
    icon: homeIcon,
    activeIcon: homeIconActive,
    scope: 'both',
  },
  {
    path: '/trunks',
    label: '线路管理',
    icon: seatsIcon,
    activeIcon: seatsIconActive,
    scope: 'admin',
  },
  {
    path: '/scripts',
    label: '话术配置',
    icon: tapeIcon,
    activeIcon: tapeIconActive,
    scope: 'both',
  },
  {
    path: '/tasks',
    label: '任务运行',
    icon: recordIcon,
    activeIcon: recordIconActive,
    scope: 'both',
  },
  {
    path: '/media',
    label: '录音管理',
    icon: expenseIcon,
    activeIcon: expenseIconActive,
    scope: 'both',
  },
  {
    path: '/contacts',
    label: '名单管理',
    icon: seatsIcon,
    activeIcon: seatsIconActive,
    scope: 'both',
  },
  {
    path: '/storage',
    label: '存储配置',
    icon: tapeIcon,
    activeIcon: tapeIconActive,
    scope: 'admin',
  },
  {
    path: '/providers',
    label: '语音接口',
    icon: recordIcon,
    activeIcon: recordIconActive,
    scope: 'admin',
  },
  {
    path: '/qc',
    label: '质检规则',
    icon: expenseIcon,
    activeIcon: expenseIconActive,
    scope: 'admin',
  },
  {
    path: '/system',
    label: '系统信息',
    icon: homeIcon,
    activeIcon: homeIconActive,
    scope: 'admin',
  },
  {
    path: '/users',
    label: '用户管理',
    icon: switchIcon,
    activeIcon: switchIconActive,
    scope: 'admin',
  },
  {
    path: '/runtime',
    label: '运行调试',
    icon: switchIcon,
    activeIcon: switchIconActive,
    scope: 'both',
  },
]
