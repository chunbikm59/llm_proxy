<script setup lang="ts">
interface Props { colspan?: number }
defineProps<Props>()
</script>
<template>
  <tr>
    <td :colspan="colspan" class="py-16 text-center text-muted-foreground">
      <slot />
    </td>
  </tr>
</template>
