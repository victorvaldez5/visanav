<script setup lang="ts">
import {onMounted, ref, watch} from "vue";
import {networkService, type Organization} from "@/services/networkService.ts";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {toast} from "vue-sonner";
import {usePagination} from "@/composables/usePagination.ts";
import PaginationBar from "@/components/interface/PaginationBar.vue";
import Icon from "@/components/ui/Icon.vue";

const {items, load, page, count, setPageData} = usePagination({
  initialPage: 1,
  accumulate: false,
  fetchPage: networkService.getOrganizations
});
const networkOrganizations = ref<Organization[]>([]);
const searchText = ref("");
const loading = ref(false);

// A short, friendly label for the org's cost to the user.
function costLabel(organization: Organization): string | null {
  if (organization.pro_bono) return "Pro bono";
  const map: Record<string, string> = {
    free: "Free",
    "sliding-scale": "Sliding scale",
    "low-cost": "Low cost",
  };
  return map[organization.fee_model] ?? null;
}

watch(searchText, async (newVal) => {
  loading.value = true;
  if (newVal === "") {
    await load(1)
    loading.value = false;
    return
  }
  if (newVal.length > 3) {
    const data = await networkService.getOrganizations(page.value, {search: searchText.value});
    setPageData(data, false);
    networkOrganizations.value = items.value;
    loading.value = false;
  }
})
onMounted(async () => {
  try {
    loading.value = true;
    await load(1)
    networkOrganizations.value = items.value;
    loading.value = false;
  } catch (e) {
    console.error(e);
    toast.error("Oops, an error occurred")
  }
})

async function handleLoadPage(newPage: number) {
  try {
    loading.value = true;
    await load(newPage)
    networkOrganizations.value = items.value;
    loading.value = false;
  } catch (e) {
    console.error(e);
    toast.error("Oops, an error occurred")
  }
}
</script>

<template>
  <div class="px-5 pb-5">
    <div class="md:flex md:items-center md:justify-between">
      <div class="min-w-0 flex-1">
        <h2 class="text-2xl/7 font-normal text-gray-800 sm:truncate sm:text-3xl sm:tracking-tight">
          Find free &amp; low-cost immigration help
        </h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Nonprofit, pro-bono, and DOJ-recognized organizations near you.
        </p>
      </div>
    </div>

    <div class="flex gap-2 mb-4 sm:mb-6 lg:mb-8 mt-4">
      <Input
        v-model="searchText"
        placeholder="Search for an organization"
      />
      <Button>Filter</Button>
    </div>
    <div
      v-if="networkOrganizations.length > 0 && !loading"
      class="divide-y divide-gray-200 dark:divide-white/10"
    >
      <ul
        role="list"
        class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 mb-4"
      >
        <li
          v-for="organization in networkOrganizations"
          :key="organization.id"
          class="col-span-1 divide-y divide-border rounded-xl bg-card text-card-foreground shadow-elevation-1"
        >
          <div class="flex w-full items-center justify-between space-x-6 p-6">
            <div class="flex-1 truncate">
              <div class="flex items-center space-x-3">
                <h3 class="truncate text-base font-medium text-gray-900 dark:text-white">
                  {{ organization.name }}
                </h3>
                <Badge
                  v-if="costLabel(organization)"
                  variant="info"
                >
                  {{ costLabel(organization) }}
                </Badge>
              </div>
              <p class="mt-1 truncate text-sm text-muted-foreground">
                {{ organization.organization_type }}
              </p>
            </div>
          </div>
          <div class="p-6">
            <div class="flex flex-col items-start space-y-1">
              <template v-if="organization.address">
                <h5 class="font-medium">
                  {{ organization.address.subdivision?.name || organization.address.city }}
                </h5>
                <p>{{ organization.address.line1 }}</p>
                <span>
                  {{ organization.address.city }}<template v-if="organization.address.subdivision">, {{ organization.address.subdivision.name }}</template>
                  {{ organization.address.postal_code }}
                </span>
              </template>
              <p
                v-else-if="organization.description"
                class="text-sm text-muted-foreground line-clamp-3"
              >
                {{ organization.description }}
              </p>
            </div>
          </div>
          <div>
            <div class="-mt-px flex divide-x divide-gray-300 dark:divide-white/10">
              <div class="flex w-0 flex-1">
                <a
                  v-if="organization.emails.length"
                  :href="`mailto:${organization.emails[0]}`"
                  class="relative -mr-px inline-flex w-0 flex-1 items-center justify-center gap-x-3 rounded-bl-lg border border-transparent py-4 text-sm font-semibold text-gray-900 dark:text-white"
                >
                  <Icon
                    name="icon-mail"
                    class="size-5 text-gray-400 dark:text-gray-500"
                  />
                  Email
                </a>
              </div>
              <div class="-ml-px flex w-0 flex-1">
                <a
                  v-if="organization.phones.length"
                  :href="`tel:${organization.phones[0]}`"
                  class="relative inline-flex w-0 flex-1 items-center justify-center gap-x-3 border border-transparent py-4 text-sm font-semibold text-gray-900 dark:text-white"
                >
                  <Icon
                    name="icon-device-smartphone"
                    class="size-5 text-gray-400 dark:text-gray-500"
                  />
                  Call
                </a>
              </div>
              <div class="-ml-px flex w-0 flex-1">
                <a
                  v-if="organization.websites.length"
                  :href="organization.websites[0]"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="relative inline-flex w-0 flex-1 items-center justify-center gap-x-3 rounded-br-lg border border-transparent py-4 text-sm font-semibold text-gray-900 dark:text-white"
                >
                  <Icon
                    name="icon-globe"
                    class="size-5 text-gray-400 dark:text-gray-500"
                  />
                  Website
                </a>
              </div>
            </div>
          </div>
        </li>
      </ul>
      <PaginationBar
        :current-page="page"
        :total="count || 1"
        @page-change="handleLoadPage"
      />
    </div>
  </div>
</template>

<style scoped>

</style>
