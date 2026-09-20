import { describe, it, expect, vi } from "vitest";
import { usePagination, type PaginatedResponse } from "@/composables/usePagination";

// Build a DRF-style paginated response. `next`/`previous` are truthy URLs when
// there is an adjacent page, which is all the composable inspects.
function page<T>(
  results: T[],
  { count = results.length, next = null as string | null, previous = null as string | null } = {},
): PaginatedResponse<T> {
  return { count, next, previous, results };
}

describe("usePagination — initial state", () => {
  it("starts empty and not loading", () => {
    const { items, page, count, loading, error, hasNext, hasPrevious, totalPages } =
      usePagination<number>({ fetchPage: async () => page([]) });

    expect(items.value).toEqual([]);
    expect(page.value).toBe(1);
    expect(count.value).toBe(0);
    expect(loading.value).toBe(false);
    expect(error.value).toBe(null);
    expect(hasNext.value).toBe(false);
    expect(hasPrevious.value).toBe(false);
    expect(totalPages.value).toBe(null);
  });

  it("honors initialPage", () => {
    const { page } = usePagination<number>({ fetchPage: async () => page([]), initialPage: 3 });
    expect(page.value).toBe(3);
  });
});

describe("usePagination — load (replace mode)", () => {
  it("populates items and derives state from the response", async () => {
    const fetchPage = vi.fn(async () =>
      page([1, 2, 3], { count: 9, next: "/api/x?page=2", previous: null }),
    );
    const p = usePagination<number>({ fetchPage });

    await p.load();

    expect(fetchPage).toHaveBeenCalledWith(1);
    expect(p.items.value).toEqual([1, 2, 3]);
    expect(p.count.value).toBe(9);
    expect(p.pageSize.value).toBe(3);
    expect(p.totalPages.value).toBe(3); // ceil(9 / 3)
    expect(p.hasNext.value).toBe(true);
    expect(p.hasPrevious.value).toBe(false);
    expect(p.loading.value).toBe(false);
  });

  it("replaces items on a subsequent load when not accumulating", async () => {
    const fetchPage = vi.fn(async (n: number) =>
      n === 1
        ? page([1, 2], { count: 4, next: "/n" })
        : page([3, 4], { count: 4, previous: "/p" }),
    );
    const p = usePagination<number>({ fetchPage });

    await p.load(1);
    await p.load(2);

    expect(p.items.value).toEqual([3, 4]);
    expect(p.page.value).toBe(2);
  });

  it("toggles loading around the fetch", async () => {
    let resolveFetch: (v: PaginatedResponse<number>) => void = () => {};
    const p = usePagination<number>({
      fetchPage: () => new Promise((res) => { resolveFetch = res; }),
    });

    const pending = p.load();
    expect(p.loading.value).toBe(true);

    resolveFetch(page([1]));
    await pending;
    expect(p.loading.value).toBe(false);
  });
});

describe("usePagination — accumulate mode", () => {
  it("appends pages after the first when accumulate is set", async () => {
    const fetchPage = vi.fn(async (n: number) =>
      n === 1
        ? page([1, 2], { count: 6, next: "/n" })
        : page([3, 4], { count: 6, next: "/n2", previous: "/p" }),
    );
    const p = usePagination<number>({ fetchPage, accumulate: true });

    await p.load(1);
    expect(p.items.value).toEqual([1, 2]);

    await p.nextPage();
    expect(p.items.value).toEqual([1, 2, 3, 4]);
    expect(p.page.value).toBe(2);
  });

  it("does not append the first page onto stale items", async () => {
    const p = usePagination<number>({
      fetchPage: async () => page([1, 2], { count: 2 }),
      accumulate: true,
    });
    await p.load(1);
    await p.load(1); // reloading page 1 replaces, never doubles
    expect(p.items.value).toEqual([1, 2]);
  });
});

describe("usePagination — navigation guards", () => {
  it("nextPage is a no-op when there is no next page", async () => {
    const fetchPage = vi.fn(async () => page([1], { count: 1 }));
    const p = usePagination<number>({ fetchPage });
    await p.load();
    fetchPage.mockClear();

    await p.nextPage();
    expect(fetchPage).not.toHaveBeenCalled();
  });

  it("prevPage is a no-op when there is no previous page", async () => {
    const fetchPage = vi.fn(async () => page([1], { count: 1, next: "/n" }));
    const p = usePagination<number>({ fetchPage });
    await p.load();
    fetchPage.mockClear();

    await p.prevPage();
    expect(fetchPage).not.toHaveBeenCalled();
  });

  it("prevPage never goes below page 1", async () => {
    const fetchPage = vi.fn(async () => page([1], { count: 5, previous: "/p" }));
    const p = usePagination<number>({ fetchPage, initialPage: 1 });
    await p.load(1);
    fetchPage.mockClear();

    await p.prevPage();
    expect(fetchPage).toHaveBeenCalledWith(1); // clamped to 1, not 0
  });

  it("goTo rejects pages below 1", async () => {
    const fetchPage = vi.fn(async () => page([1]));
    const p = usePagination<number>({ fetchPage });
    await p.goTo(0);
    expect(fetchPage).not.toHaveBeenCalled();
  });

  it("loadMore delegates to nextPage only when a next page exists", async () => {
    const fetchPage = vi.fn(async (n: number) =>
      n === 1 ? page([1], { count: 2, next: "/n" }) : page([2], { count: 2, previous: "/p" }),
    );
    const p = usePagination<number>({ fetchPage });
    await p.load(1);
    await p.loadMore();
    expect(p.page.value).toBe(2);

    fetchPage.mockClear();
    await p.loadMore(); // now no next → no fetch
    expect(fetchPage).not.toHaveBeenCalled();
  });
});

describe("usePagination — error handling", () => {
  it("captures a rejected fetch and clears loading", async () => {
    const boom = new Error("network down");
    const p = usePagination<number>({ fetchPage: async () => { throw boom; } });

    await p.load();

    expect(p.error.value).toBe(boom);
    expect(p.loading.value).toBe(false);
    expect(p.items.value).toEqual([]);
  });

  it("clears a prior error on the next successful load", async () => {
    let fail = true;
    const p = usePagination<number>({
      fetchPage: async () => {
        if (fail) throw new Error("nope");
        return page([1]);
      },
    });

    await p.load();
    expect(p.error.value).toBeInstanceOf(Error);

    fail = false;
    await p.load();
    expect(p.error.value).toBe(null);
    expect(p.items.value).toEqual([1]);
  });
});

describe("usePagination — reset", () => {
  it("returns to a clean slate", async () => {
    const p = usePagination<number>({
      fetchPage: async () => page([1, 2], { count: 8, next: "/n", previous: "/p" }),
    });
    await p.load(2);
    expect(p.items.value.length).toBe(2);

    p.reset();

    expect(p.items.value).toEqual([]);
    expect(p.page.value).toBe(1);
    expect(p.count.value).toBe(0);
    expect(p.next.value).toBe(null);
    expect(p.previous.value).toBe(null);
    expect(p.pageSize.value).toBe(null);
    expect(p.error.value).toBe(null);
  });

  it("can reset to a specific page", async () => {
    const p = usePagination<number>({ fetchPage: async () => page([]) });
    p.reset(5);
    expect(p.page.value).toBe(5);
  });
});

describe("usePagination — totalPages", () => {
  it("is null until a page size is known", () => {
    const { totalPages } = usePagination<number>({ fetchPage: async () => page([]) });
    expect(totalPages.value).toBe(null);
  });

  it("rounds up partial final pages", async () => {
    const p = usePagination<number>({
      fetchPage: async () => page([1, 2, 3, 4, 5], { count: 12 }),
    });
    await p.load();
    expect(p.totalPages.value).toBe(3); // ceil(12 / 5)
  });
});
