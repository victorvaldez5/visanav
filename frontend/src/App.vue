<template>
  <Toaster rich-colors />
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset class="h-svh min-h-0 overflow-hidden">
      <BetaBanner class="shrink-0" />
      <header class="flex shrink-0 py-4 px-5 gap-3">
        <SidebarTrigger />
        <Separator
          orientation="vertical"
          class="mr-2 h-5"
        />
      </header>
      <!-- The shell is bound to the viewport so the chat can scroll only its
           conversation; every other page scrolls inside this region instead. -->
      <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <RouterView />
      </div>
      <slot />
    </SidebarInset>
  </SidebarProvider>
</template>

<script setup lang="ts">
import {SidebarProvider, SidebarInset, SidebarTrigger} from "@/components/ui/sidebar";
import {Separator} from "@/components/ui/separator";
import {RouterView} from 'vue-router'
import AppSidebar from "@/components/interface/AppSidebar.vue";
import BetaBanner from "@/components/interface/BetaBanner.vue";
// Eagerly initialize the app-wide light/dark theme at the root, so the
// persisted/OS theme is applied to <html> regardless of which child renders.
import "@/composables/useTheme";
import {breakpointsTailwind, useBreakpoints} from "@vueuse/core";
import {provide} from "vue";
import {Toaster} from 'vue-sonner';
import 'vue-sonner/style.css'

const breakpoints = useBreakpoints(breakpointsTailwind)

const activeBreakpoint = breakpoints.active()
const isMobile = breakpoints.smaller('md')

provide('isMobile', isMobile);
provide('activeBreakpoint', activeBreakpoint);
</script>
