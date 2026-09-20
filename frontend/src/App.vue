<template>
  <Toaster rich-colors />
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset>
      <BetaBanner />
      <header class="flex py-4 px-5 gap-3">
        <SidebarTrigger />
        <Separator orientation="vertical" class="mr-2 h-5" />
      </header>
      <RouterView />
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
