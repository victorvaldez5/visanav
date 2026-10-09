import {computed, onMounted} from "vue";
import {watchDebounced} from "@vueuse/core";
import {toast} from "vue-sonner";
import {usePagination, type PaginatedResponse} from "@/composables/usePagination.ts";

// Shared filter/list orchestration for the resource-directory views. Given a
// `buildFilters` snapshot and a page fetcher, it wires pagination, collapses
// every filter change into a single debounced reload from page 1, loads once on
// mount, and surfaces failures as a toast. Each page keeps its own filter refs
// and `buildFilters`; only this boilerplate is shared.
export function useDirectoryFilters<T, F>(opts: {
  buildFilters: () => F;
  fetchPage: (page: number, filters: F) => Promise<PaginatedResponse<T>>;
  errorMessage: () => string;
}) {
  const {items, load, page, count, loading} = usePagination<T>({
    fetchPage: (p) => opts.fetchPage(p, opts.buildFilters()),
  });

  function reload(p = 1) {
    load(p).catch((e) => {
      console.error(e);
      toast.error(opts.errorMessage());
    });
  }

  const filterKey = computed(() => JSON.stringify(opts.buildFilters()));
  watchDebounced(filterKey, () => reload(1), {debounce: 250});

  onMounted(() => reload(1));

  return {items, page, count, loading, reload};
}
