<script setup lang="ts">
import { EOIR_ROSTER_URL } from "@/i18n";

// Short disclaimer shown at the start of each conversation (and the new-chat
// welcome), reinforcing the persistent banner without repeating it in full.
</script>

<template>
  <p class="px-2 text-center text-xs leading-4 text-muted-foreground">
    <i18n-t
      keypath="disclaimer.short"
      tag="span"
      scope="global"
    >
      <template #rep>
        <a
          :href="EOIR_ROSTER_URL"
          target="_blank"
          rel="noopener noreferrer"
          class="underline underline-offset-2 hover:no-underline"
        >{{ $t("rep") }}</a>
      </template>
    </i18n-t>
  </p>
</template>
