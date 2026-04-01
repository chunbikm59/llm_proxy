<script setup lang="ts">
interface Props { open?: boolean }
defineProps<Props>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()
</script>

<template>
  <Teleport to="body">
    <template v-if="open">
      <slot />
    </template>
  </Teleport>
</template>
