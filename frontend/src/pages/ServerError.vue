<!-- src/pages/ErrorFallback.vue -->
<template>
  <main class="min-h-[50vh] grid place-items-center p-6">
    <section class="text-center">
      <div class="mx-auto mb-4 h-10 w-10 rounded-full border-2 border-gray-300 border-t-black animate-spin" />
      <h2 class="text-xl font-semibold">
        {{ t("common.loading") }}
      </h2>
      <p
        v-if="!minimal"
        class="text-gray-600 mt-2"
      >
        {{ t("errors.slowLoad") }}
      </p>

      <div
        v-if="error"
        class="mt-4 text-sm text-red-600"
      >
        {{ errorMessage }}
      </div>

      <div class="mt-6">
        <RouterLink
          to="/"
          class="text-sm text-blue-600 hover:underline"
        >
          {{ t("common.backHome") }}
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import {useI18n} from 'vue-i18n'

interface Props {
  error?: unknown
  minimal?: boolean
}

const {t} = useI18n()
const props = defineProps<Props>()

const errorMessage = computed(() => {
  if (!props.error) return ''
  if (props.error instanceof Error) return props.error.message
  try {
    return JSON.stringify(props.error)
  } catch {
    return String(props.error)
  }
})
</script>

<style scoped>
/* fallback spinner if Tailwind plugin isn’t active */
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
