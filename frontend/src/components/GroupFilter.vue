<template>
  <a-segmented
    class="group-filter"
    :value="modelValue"
    :options="options"
    @change="handleChange"
  />
</template>

<script setup lang="ts">
interface GroupOption {
  label: string;
  value: string;
}

defineProps<{
  modelValue: string;
  options: GroupOption[];
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
  change: [value: string];
}>();

function handleChange(value: string | number) {
  const nextValue = String(value);
  emit('update:modelValue', nextValue);
  emit('change', nextValue);
}
</script>

