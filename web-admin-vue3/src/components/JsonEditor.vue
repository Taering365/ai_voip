<template>
  <el-input
    :model-value="modelValue"
    type="textarea"
    :rows="rows"
    :placeholder="placeholder"
    @update:model-value="emitValue"
  />
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: '{}',
  },
  rows: {
    type: Number,
    default: 8,
  },
  placeholder: {
    type: String,
    default: '请输入 JSON 文本',
  },
})

const emit = defineEmits(['update:modelValue'])

/**
 * 将输入框最新内容回传给父组件。
 *
 * @param {string} value 用户输入的 JSON 文本。
 * @returns {void}
 */
function emitValue(value) {
  void props
  emit('update:modelValue', value)
}
</script>
