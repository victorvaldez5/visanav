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
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import ConversationsSidebarGroup from "@/components/interface/ConversationsSidebarGroup.vue";
import { useAuthStore } from "@/stores/useAuthStore.ts";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/ui/Icon.vue";
import ThemeToggle from "@/components/interface/ThemeToggle.vue";
import LanguageSwitcher from "@/components/interface/LanguageSwitcher.vue";
import { useTheme } from "@/composables/useTheme";
import logoLight from "@/assets/VisaNav-Horizontal-Main.svg";
import logoDark from "@/assets/VisaNav-Horizontal-OnDark.svg";

const { t } = useI18n();
const { isDark } = useTheme();

const authStore = useAuthStore();
const { isAuthenticated, username, userId,  userEmail} = storeToRefs(authStore);
const { logout } = authStore;
const route = useRoute();

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
      <img
        :alt="t('nav.logoAlt')"
        class="h-7 w-fit"
        :src="isDark ? logoDark : logoLight"
      >
      <ThemeToggle />
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
                <div
                  v-if="isAuthenticated"
                  class="flex items-center"
                >
                  <Avatar>
                    <AvatarImage
                      src="https://github.com/unovue.png"
                      alt="@unovue"
                    />
                    <AvatarFallback>CN</AvatarFallback>
                  </Avatar>
                  <div class="flex flex-col px-2">
                    <div class="text-lg font-medium">
                      {{ username }}
                    </div>
                    <div class="text-xs  font-normal">
                      {{ userEmail }}
                    </div>
                  </div>
                </div>
                <template v-else>
                  <RouterLink to="Login">
                    {{ t("nav.signIn") }}
                  </RouterLink>
                </template>
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
            </DropdownMenuContent>
          </DropdownMenu>
          <template v-else>
            <SidebarMenuButton as-child>
              <RouterLink to="register">
                {{ t("nav.register") }}
              </RouterLink>
            </SidebarMenuButton>
            <SidebarMenuButton as-child>
              <RouterLink
                to="login"
                class="sidebar-accent-foreground"
              >
                {{ t("nav.login") }}
              </RouterLink>
            </SidebarMenuButton>
          </template>
        </SidebarMenuItem>
      </SidebarMenu>
      <LanguageSwitcher class="mt-2" />
      <nav
        :aria-label="t('nav.legal')"
        class="mt-1 flex items-center justify-center gap-2 px-2 text-xs text-muted-foreground"
      >
        <a
          href="https://www.visanav.org/terms"
          target="_blank"
          rel="noopener"
          class="hover:underline"
        >{{ t("nav.terms") }}</a>
        <span aria-hidden="true">·</span>
        <a
          href="https://www.visanav.org/privacy"
          target="_blank"
          rel="noopener"
          class="hover:underline"
        >{{ t("nav.privacy") }}</a>
      </nav>
    </SidebarFooter>
  </Sidebar>
</template>
