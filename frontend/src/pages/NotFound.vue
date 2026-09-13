<!-- src/pages/NotFound.vue -->
<template>
  <main class="min-h-screen grid place-items-center bg-white text-gray-800 p-6">
    <section class="text-center">
      <h1 class="text-6xl font-bold">
        404
      </h1>
      <p class="mt-4 text-lg text-gray-600">
        The page you’re looking for doesn’t exist.
      </p>

      <div class="mt-8 flex justify-center gap-3">
        <RouterLink
          to="/"
          class="px-4 py-2 rounded-md bg-black text-white hover:bg-gray-800 transition"
        >
          Go Home
        </RouterLink>
        <button
          class="px-4 py-2 rounded-md border border-gray-300 hover:bg-gray-50 transition"
          @click="goBack"
        >
          Go Back
        </button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import {useRouter} from 'vue-router'

const router = useRouter()
const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>
