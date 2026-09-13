<script setup lang="ts">
import {onMounted, ref, watch} from "vue";
import {networkService, type Organization} from "@/services/networkService.ts";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
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
          Search our Network
        </h2>
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
          class="col-span-1 divide-y divide-gray-300 rounded-lg bg-card text-card-foreground shadow-sm dark:divide-white/10 dark:bg-gray-800/50 dark:shadow-none dark:outline dark:-outline-offset-1 dark:outline-white/10"
        >
          <div class="flex w-full items-center justify-between space-x-6 p-6">
            <div class="flex-1 truncate">
              <div class="flex items-center space-x-3">
                <h3 class="truncate text-base font-medium text-gray-900 dark:text-white">
                  {{ organization.name }}
                </h3>
              </div>
              <p class="mt-1 truncate text-sm text-muted-foreground">
                {{ organization.organization_type }}
              </p>
            </div>
          </div>
          <div class="p-6">
            <div class="flex flex-col items-center space-x-3">
              <template
                v-for="orgAddress in organization.addresses"
                :key="orgAddress.id"
              >
                <div
                  v-if="orgAddress.is_primary"
                  class="w-full mb-4"
                >
                  <h5>{{ orgAddress.address?.address_name || 'Primary Office' }}</h5>
                  <p>
                    {{ orgAddress.address.line1 }}
                  </p>
                  <span>{{ orgAddress.address.city }}, {{
                    orgAddress.address.subdivision.name
                  }}, {{ orgAddress.address.postal_code }}</span>
                </div>
              </template>
            </div>
          </div>
          <div>
            <div class="-mt-px flex divide-x divide-gray-300 dark:divide-white/10">
              <div class="flex w-0 flex-1">
                <a
                  :href="`mailto:${organization.emails}`"
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
                  :href="`tel:${organization.phone_numbers[0]?.phone_number}`"
                  class="relative inline-flex w-0 flex-1 items-center justify-center gap-x-3 rounded-br-lg border border-transparent py-4 text-sm font-semibold text-gray-900 dark:text-white"
                >
                  <Icon
                    name="icon-device-smartphone"
                    class="size-5 text-gray-400 dark:text-gray-500"
                  />
                  Call
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
