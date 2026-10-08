<!-- src/pages/NotFound.vue -->
<template>
  <main class="min-h-screen grid place-items-center bg-white text-gray-800 p-6">
    <section class="text-center">
      <h1 class="text-6xl font-bold">
        404
      </h1>
      <p class="mt-4 text-lg text-gray-600">
        {{ t("errors.notFoundBody") }}
      </p>

      <div class="mt-8 flex justify-center gap-3">
        <RouterLink
          to="/"
          class="px-4 py-2 rounded-md bg-black text-white hover:bg-gray-800 transition"
        >
          {{ t("common.home") }}
        </RouterLink>
        <button
          class="px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-200 transition"
          @click="goBack"
        >
          {{ t("common.back") }}
        </button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import {useRouter} from 'vue-router'
import {useI18n} from 'vue-i18n'

const {t} = useI18n()
const router = useRouter()
const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>
