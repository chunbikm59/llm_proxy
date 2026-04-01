<script setup lang="ts">
import { cn } from '@/lib/utils'
interface Props { class?: string; colspan?: number }
const props = defineProps<Props>()
</script>
<template>
  <td :colspan="colspan" :class="cn('px-3 py-2 align-middle [&:has([role=checkbox])]:pr-0', props.class)">
    <slot />
  </td>
</template>
