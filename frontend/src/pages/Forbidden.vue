<template>
  <main class="min-h-screen grid place-items-center bg-white text-gray-800 p-6">
    <section class="text-center max-w-lg">
      <h1 class="text-5xl font-bold">
        403
      </h1>
      <h2 class="mt-2 text-xl font-semibold">
        Permission denied
      </h2>
      <p class="mt-3 text-gray-600">
        You don’t have permission to view this page.
      </p>

      <div class="mt-8 flex justify-center gap-3">
        <RouterLink
          to="/"
          class="px-4 py-2 rounded-md bg-black text-white hover:bg-gray-800 transition"
        >
          Go Home
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
</script>
