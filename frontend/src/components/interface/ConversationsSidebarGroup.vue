<script setup lang="ts">
import {onMounted, ref, watch} from "vue";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem
} from "@/components/ui/sidebar";
import {conversationService} from "@/services/conversationService.ts";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {useRoute} from "vue-router";
import {usePagination} from "@/composables/usePagination.ts";

const authStore = useAuthStore()
const {isAuthenticated} = storeToRefs(authStore)
const route = useRoute()

const {items, load} = usePagination({
  accumulate: true,
  initialPage: 1,
  fetchPage: conversationService.getAllConversations
})
const conversations: any = ref([]);

watch(isAuthenticated, async () => {
  await getConversations();
}, {immediate: true});

onMounted(async () => {
  await getConversations()
})

async function getConversations() {
  if (!isAuthenticated.value) {
    conversations.value = [];
    return
  }
  await load(1)
  conversations.value = items.value
}
</script>

<template>
  <SidebarGroup v-if="conversations.length > 0">
    <SidebarGroupLabel class="text-sm font-semibold leading-loose tracking-wide">Conversations</SidebarGroupLabel>
    <SidebarGroupContent>
      <SidebarMenu>
        <SidebarMenuItem
          v-for="convo in conversations"
          :key="convo.id"
        >
          <SidebarMenuButton
            as-child
            class="text-base"
            :is-active="convo.uuid === route.params.conversationUuid"
          >
            <RouterLink :to="`/conversations/${convo?.uuid}`">
              {{ 'Conversation ' + convo?.id }}
            </RouterLink>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroupContent>
  </SidebarGroup>
</template>

<style scoped>

</style>
