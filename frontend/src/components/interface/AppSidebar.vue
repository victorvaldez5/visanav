<script setup lang="ts">
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import ConversationsSidebarGroup from "@/components/interface/ConversationsSidebarGroup.vue";
import { useAuthStore } from "@/stores/useAuthStore.ts";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSidebar } from "@/components/ui/sidebar";
import LeaveChatDialog from "@/components/interface/LeaveChatDialog.vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/ui/Icon.vue";
import ThemeMenuItem from "@/components/interface/ThemeMenuItem.vue";
import LanguageMenu from "@/components/interface/LanguageMenu.vue";
import { useTheme } from "@/composables/useTheme";
import logoLight from "@/assets/VisaNav-Horizontal-Main.svg";
import logoDark from "@/assets/VisaNav-Horizontal-OnDark.svg";

const { t } = useI18n();
const { isDark } = useTheme();

const authStore = useAuthStore();
const { isAuthenticated, displayName, userId, userEmail } = storeToRefs(authStore);
const { logout } = authStore;
// Initial for the avatar. No remote image: it would send every signed-in user's
// IP to a third-party host, which a privacy-first app shouldn't do.
const initial = computed(() => displayName.value.charAt(0).toUpperCase() || "?");
const route = useRoute();
const router = useRouter();
const { setOpenMobile } = useSidebar();

// The logo goes to the landing page. From an open conversation that starts a
// new chat, so it first confirms and offers the conversation's link.
const homeHref = computed(() => router.resolve("/").href);
const leaveOpen = ref(false);
const conversationUrl = computed(() => window.location.origin + route.fullPath);

function onLogoClick(e: MouseEvent) {
    // Let the browser handle opening in a new tab or window.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (route.name === "Conversation") {
        leaveOpen.value = true;
    } else {
        goHome();
    }
}

function goHome() {
    setOpenMobile(false);
    void router.push("/");
}

const menuItems = computed(() => [
    {
        title: t("nav.newChat"),
        icon: "icon-edit",
        href: "/",
    },
    {
        title: t("nav.resources"),
        icon: "icon-scale",
        href: "/resources",
    },
    {
        title: t("nav.representatives"),
        icon: "icon-user-check",
        href: "/representatives",
    },
    {
      title: t("nav.forms"),
      icon: "icon-folder",
      href: "/forms",
    },
]);
</script>

<template>
  <Sidebar>
    <SidebarHeader class="flex flex-row items-center justify-between py-6 px-4">
      <a
        :href="homeHref"
        :aria-label="t('nav.home')"
        class="rounded-md outline-none focus-visible:shadow-glow-focus"
        @click="onLogoClick"
      >
        <img
          :alt="t('nav.logoAlt')"
          class="h-7 w-fit"
          :src="isDark ? logoDark : logoLight"
        >
      </a>
      <LanguageMenu />
      <LeaveChatDialog
        v-model:open="leaveOpen"
        :url="conversationUrl"
        @leave="goHome"
      />
    </SidebarHeader>
    <SidebarContent class="py-2">
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem
              v-for="item in menuItems"
              :key="item.title"
              class="mb-2"
            >
              <SidebarMenuButton
                as-child
                :is-active="item.href === route.path"
              >
                <RouterLink :to="item.href">
                  <Icon
                    :name="item.icon"
                    class="w-4 h-4"
                  />
                  <span class="text-base">{{ item.title }}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
      <ConversationsSidebarGroup />
    </SidebarContent>
    <SidebarFooter class="py-4">
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu v-if="isAuthenticated">
            <DropdownMenuTrigger as-child>
              <SidebarMenuButton class="py-7 px-2 bg-background items-center gap-3">
                <div class="flex items-center">
                  <Avatar>
                    <AvatarFallback>{{ initial }}</AvatarFallback>
                  </Avatar>
                  <div class="flex min-w-0 flex-col px-2">
                    <div class="truncate">
                      {{ displayName || t("nav.account") }}
                    </div>
                    <div
                      v-if="userEmail && userEmail !== displayName"
                      class="truncate text-xs font-normal"
                    >
                      {{ userEmail }}
                    </div>
                  </div>
                </div>
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="top"
              class="w-3xs"
            >
              <DropdownMenuItem
                as-child
                class="text-base"
              >
                <RouterLink :to="`/profile/${userId}`">
                  {{ t("nav.account") }}
                </RouterLink>
              </DropdownMenuItem>
              <DropdownMenuItem
                class="text-base"
                @click="logout()"
              >
                <span>{{ t("nav.signOut") }}</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <ThemeMenuItem />
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu v-else>
            <DropdownMenuTrigger as-child>
              <SidebarMenuButton class="py-7 px-2 bg-background items-center justify-center text-base font-medium">
                {{ t("nav.registerLogin") }}
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="top"
              class="w-3xs"
            >
              <DropdownMenuItem
                as-child
                class="text-base"
              >
                <RouterLink to="/register">
                  {{ t("nav.register") }}
                </RouterLink>
              </DropdownMenuItem>
              <DropdownMenuItem
                as-child
                class="text-base"
              >
                <RouterLink to="/login">
                  {{ t("nav.login") }}
                </RouterLink>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <ThemeMenuItem />
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
      <nav
        :aria-label="t('nav.legal')"
        class="mt-1 flex items-center justify-center gap-2 px-2 text-xs text-muted-foreground"
      >
        <a
          href="https://www.visanav.org/terms"
          target="_blank"
          rel="noopener noreferrer"
          class="hover:underline"
        >{{ t("nav.terms") }}</a>
        <span aria-hidden="true">·</span>
        <a
          href="https://www.visanav.org/privacy"
          target="_blank"
          rel="noopener noreferrer"
          class="hover:underline"
        >{{ t("nav.privacy") }}</a>
      </nav>
    </SidebarFooter>
  </Sidebar>
</template>
