import {computed, ref, shallowRef} from "vue";

export interface PaginatedResponse<T> {
    count: number;
    next: string | null;
    previous: string | null;
    results: T[];
}

type FetchPageFn<T> = (page: number) => Promise<PaginatedResponse<T>>;

export interface UsePaginationOptions<T> {
    fetchPage: FetchPageFn<T>;
    // Start page (default 1)
    initialPage?: number;
    // If true, appends items when calling nextPage/loadMore; otherwise replaces
    accumulate?: boolean;
}

export function usePagination<T>(options: UsePaginationOptions<T>) {
    const {
        initialPage = 1,
        accumulate = false,
    } = options;

    // State
    const items = shallowRef<T[]>([]);
    const page = ref<number>(initialPage);
    const pageSize = ref<number | null>(null);
    const count = ref<number>(0);
    const next = ref<string | null>(null);
    const previous = ref<string | null>(null);
    const loading = ref<boolean>(false);
    const error = ref<unknown>(null);

    // Derived
    const hasNext = computed(() => next.value !== null);
    const hasPrevious = computed(() => previous.value !== null);
    const totalPages = computed(() => {
        if (pageSize.value && pageSize.value > 0) {
            return Math.ceil(count.value / pageSize.value);
        }
        return null;
    });

    // Helpers
    function setPageData(resp: PaginatedResponse<T>, append: boolean) {
        count.value = resp.count;
        next.value = resp.next;
        previous.value = resp.previous;

        // derive page size dynamically; DRF can vary but typically fixed per view
        pageSize.value = resp.results.length || pageSize.value || null;

        if (append) {
            const {results} = resp;
            items.value = items.value.concat(results);
        } else {
            items.value = resp.results
        }
    }

    async function load(requestedPage?: number) {
        loading.value = true;
        error.value = null;

        const targetPage = requestedPage ?? page.value;

        try {
            const resp = await options.fetchPage(targetPage);
            // If caller provided a page explicitly, keep state in sync
            page.value = targetPage;

            // Append or replace depending on accumulate flag and whether this is the first page loaded
            const shouldAppend = accumulate && items.value.length > 0 && targetPage > 1;
            setPageData(resp, shouldAppend);
        } catch (e) {
            error.value = e;
        } finally {
            loading.value = false;
        }
    }

    async function nextPage() {
        if (!hasNext.value) return;
        const nextPageNumber = page.value + 1;
        await load(nextPageNumber);
    }

    async function prevPage() {
        if (!hasPrevious.value) return;
        const prevPageNumber = Math.max(1, page.value - 1);
        await load(prevPageNumber);
    }

    async function goTo(targetPage: number) {
        if (targetPage < 1) return;
        await load(targetPage);
    }

    async function loadMore() {
        // Convenience for infinite lists
        if (hasNext.value) {
            await nextPage();
        }
    }

    function reset(newPage: number = 1) {
        items.value = [];
        page.value = newPage;
        count.value = 0;
        next.value = null;
        previous.value = null;
        pageSize.value = null;
        error.value = null;
    }

    // Optionally auto-load on first use
    // await load(initialPage) — leave to caller for control

    return {
        // state
        items,
        page,
        count,
        pageSize,
        next,
        previous,
        loading,
        error,

        // derived
        hasNext,
        hasPrevious,
        totalPages,

        // actions
        load,
        nextPage,
        prevPage,
        goTo,
        setPageData,
        loadMore,
        reset,
    };
}