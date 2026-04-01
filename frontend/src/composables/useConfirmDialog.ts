import { ref } from 'vue'

const visible = ref(false)
const title = ref('')
const description = ref('')
let _resolve: ((v: boolean) => void) | null = null

export function useConfirmDialog() {
  function confirm(msg: string, desc = ''): Promise<boolean> {
    title.value = msg
    description.value = desc
    visible.value = true
    return new Promise(resolve => { _resolve = resolve })
  }

  function onConfirm() {
    visible.value = false
    _resolve?.(true)
  }

  function onCancel() {
    visible.value = false
    _resolve?.(false)
  }

  return { visible, title, description, confirm, onConfirm, onCancel }
}
