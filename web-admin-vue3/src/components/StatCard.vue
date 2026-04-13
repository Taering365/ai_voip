<template>
  <div class="stat-card page-card">
    <div>
      <div class="stat-label">{{ label }}</div>
      <div class="stat-value">{{ value }}</div>
      <div class="stat-desc">{{ description }}</div>
    </div>
    <div class="stat-icon-wrap">
      <el-icon size="28">
        <component :is="icon" />
      </el-icon>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    default: '',
  },
  value: {
    type: [String, Number],
    default: '--',
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: [Object, Function],
    default: null,
  },
})
</script>

<style scoped lang="scss">
.stat-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
}

.stat-label {
  font-size: 14px;
  color: #7181a7;
}

.stat-value {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 800;
  color: #364064;
}

.stat-desc {
  margin-top: 10px;
  font-size: 12px;
  color: #94a2c4;
}

.stat-icon-wrap {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  border-radius: 20px;
  color: #0b7cff;
  background: linear-gradient(135deg, #edf5ff 0%, #dcecff 100%);
}
</style>
