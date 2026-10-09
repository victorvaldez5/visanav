<script setup lang="ts">
import {computed, ref} from "vue";
import {useRoute, useRouter} from "vue-router";
import {useI18n} from "vue-i18n";
import {networkService, type Representative, type RepresentativeFilters} from "@/services/networkService.ts";
import {US_STATES} from "@/lib/usStates.ts";
import {useDirectoryFilters} from "@/composables/useDirectoryFilters.ts";
import {fmtDate, telHref} from "@/lib/format.ts";
import {selectClass, crossLinkClass} from "@/lib/directoryStyles.ts";
import {EOIR_ROSTER_URL} from "@/i18n";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import PaginationBar from "@/components/interface/PaginationBar.vue";
import Eyebrow from "@/components/interface/Eyebrow.vue";
import LineIcon from "@/components/interface/LineIcon.vue";
import FilterChips from "@/components/interface/FilterChips.vue";
import InfoHint from "@/components/interface/InfoHint.vue";
import FilterPanel from "@/components/interface/FilterPanel.vue";

const REP_ORDERING: Record<string, string> = {
  expiry: "-accreditation_expiration",
  name: "name",
  org: "organization__name,name",
};
const {t, tm, rt} = useI18n();
const scopeItems = computed(() => [
  {id: "full", label: t("reps.scopeFull"), hint: t("reps.scopeFullHint")},
  {id: "dhs", label: t("reps.scopeDhs"), hint: t("reps.scopeDhsHint")},
]);
const eyebrow = computed(() => (tm("reps.eyebrow") as Parameters<typeof rt>[0][]).map((m) => rt(m)));
const route = useRoute();
const router = useRouter();

const search = ref(typeof route.query.q === "string" ? route.query.q : "");
const region = ref("");
const scope = ref<Record<string, boolean>>({});
const sort = ref("expiry");

function buildFilters(): RepresentativeFilters {
  const s = scope.value;
  let dhsOnly: boolean | null = null;
  if (s.full && !s.dhs) dhsOnly = false;
  else if (s.dhs && !s.full) dhsOnly = true;
  return {
    search: search.value || null,
    region: region.value || null,
    dhsOnly,
    ordering: REP_ORDERING[sort.value] ?? "-accreditation_expiration",
  };
}

// Filters shown in the mobile sheet (search stays visible, so it isn't counted).
const activeFilterCount = computed(() => {
  const scopeCount = Object.values(scope.value).filter(Boolean).length;
  return (region.value ? 1 : 0) + scopeCount;
});

const {items, page, count, loading, reload} = useDirectoryFilters<Representative, RepresentativeFilters>({
  buildFilters,
  fetchPage: (p, f) => networkService.getRepresentatives(p, f),
  errorMessage: () => t("reps.loadError"),
});

function repLocation(rep: Representative): string | null {
  if (rep.organization_city && rep.organization_state)
    return `${rep.organization_city}, ${rep.organization_state}`;
  return rep.organization_state || rep.organization_city || null;
}
function expiryLabel(days: number): string {
  if (days <= 0) return t("reps.expiresToday");
  return t("reps.expiresIn", {n: days}, days);
}
function viewOrg(rep: Representative) {
  if (rep.organization_name) router.push({name: "Resources", query: {q: rep.organization_name}});
}
function clearFilters() {
  search.value = "";
  region.value = "";
  scope.value = {};
  sort.value = "expiry";
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1180px] px-5 pb-10">
    <!-- Page head -->
    <header class="pb-[22px] pt-4">
      <Eyebrow :parts="eyebrow" />
      <h1 class="mt-2.5 font-serif text-[30px] font-bold leading-[38px] max-sm:text-2xl max-sm:leading-8">
        {{ t("reps.title") }}
      </h1>
      <p class="mt-2.5 max-w-[66ch] text-base leading-[25px] text-muted-foreground">
        {{ t("reps.intro") }}
      </p>
    </header>

    <!-- Filters -->
    <FilterPanel :active-count="activeFilterCount">
      <template #search>
        <div class="grid min-w-0 gap-1.5">
          <label
            for="r-search"
            class="text-sm font-medium leading-none"
          >{{ t("reps.searchLabel") }}</label>
          <Input
            id="r-search"
            v-model="search"
            type="search"
            autocomplete="off"
            :placeholder="t('reps.searchPlaceholder')"
            class="h-[38px] max-md:h-[46px]"
          />
        </div>
      </template>

      <div class="grid min-w-0 gap-1.5">
        <label
          for="r-state"
          class="text-sm font-medium leading-none"
        >{{ t("common.state") }}</label>
        <select
          id="r-state"
          v-model="region"
          :class="selectClass"
        >
          <option value="">
            {{ t("common.allStates") }}
          </option>
          <option
            v-for="s in US_STATES"
            :key="s.code"
            :value="s.name"
          >
            {{ s.name }}
          </option>
        </select>
      </div>
      <div class="grid gap-[9px]">
        <div class="flex items-center gap-1.5">
          <span class="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">{{ t("common.scope") }}</span>
          <InfoHint
            :label="t('reps.scopeHintLabel')"
            :text="t('reps.scopeHint')"
          />
        </div>
        <FilterChips
          v-model="scope"
          :items="scopeItems"
          :aria-label="t('common.scope')"
        />
      </div>
    </FilterPanel>

    <!-- Toolbar -->
    <div class="flex flex-wrap items-baseline justify-between gap-4 pb-4 pt-[26px] max-md:pt-4">
      <h2 class="font-serif text-[22px] font-bold leading-[30px] max-md:text-[20px] max-md:leading-[28px]">
        {{ region ? t("reps.countIn", {count, region}, count) : t("reps.count", count) }}
      </h2>
      <div class="flex items-center gap-2 text-sm text-muted-foreground max-md:grid max-md:w-full max-md:grid-cols-[auto_1fr]">
        <label for="r-sort">{{ t("common.sortBy") }}</label>
        <select
          id="r-sort"
          v-model="sort"
          :class="[selectClass, 'md:h-[34px] md:w-auto md:text-sm']"
        >
          <option value="expiry">
            {{ t("reps.sort.expiry") }}
          </option>
          <option value="name">
            {{ t("reps.sort.name") }}
          </option>
          <option value="org">
            {{ t("reps.sort.org") }}
          </option>
        </select>
      </div>
    </div>

    <!-- Results -->
    <div
      v-if="items.length"
      class="grid gap-3.5 transition-opacity [grid-template-columns:repeat(auto-fill,minmax(min(100%,390px),1fr))]"
      :class="{'opacity-60': loading}"
    >
      <article
        v-for="rep in items"
        :key="rep.id"
        class="flex flex-col rounded-xl bg-card p-[18px] text-card-foreground shadow-elevation-1 transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-elevation-2"
      >
        <div class="flex items-start justify-between gap-3 max-md:flex-col max-md:gap-2.5">
          <div class="min-w-0">
            <h3 class="font-serif text-[17px] font-bold leading-[25px] max-md:text-[18px] max-md:leading-[26px]">
              {{ rep.name }}
            </h3>
            <p
              v-if="rep.organization_name"
              class="mt-0.5 text-[13px] leading-[18px] text-muted-foreground"
            >
              {{ rep.organization_name }}
            </p>
          </div>
          <div class="flex max-w-[52%] flex-none flex-wrap justify-end gap-1.5 max-md:max-w-full max-md:justify-start">
            <Badge :variant="rep.dhs_only ? 'info' : 'status'">
              {{ rep.dhs_only ? t("reps.scopeDhs") : t("reps.scopeFull") }}
            </Badge>
            <Badge
              v-if="rep.days_left !== null && rep.days_left <= 90"
              variant="status"
            >
              {{ expiryLabel(rep.days_left) }}
            </Badge>
          </div>
        </div>

        <div class="mt-3.5">
          <Eyebrow
            variant="muted"
            :parts="[repLocation(rep), rep.accreditation_expiration ? t('reps.accreditedThrough', {date: fmtDate(rep.accreditation_expiration)}) : null]"
          />
        </div>

        <p class="mt-3 text-[13px] leading-[19px] text-muted-foreground">
          <template v-if="rep.organization_phone">
            {{ t("reps.orgPhoneNote") }}
          </template>
          <template v-else>
            {{ t("reps.noDirect") }}
          </template>
        </p>

        <div class="mt-auto flex flex-wrap items-center gap-[9px] pt-3.5">
          <Button
            v-if="rep.organization_phone"
            as-child
            variant="default"
            size="sm"
            class="max-md:h-11 max-md:w-full"
          >
            <a :href="telHref(rep.organization_phone)">
              <LineIcon
                name="phone"
                class="h-[15px] w-[15px]"
              />
              <span class="tabular-nums">{{ rep.organization_phone }}</span>
            </a>
          </Button>
          <button
            v-if="rep.organization_name"
            type="button"
            :class="crossLinkClass"
            @click="viewOrg(rep)"
          >
            {{ t("reps.viewOrg") }} <span aria-hidden="true">→</span>
          </button>
        </div>
      </article>
    </div>

    <!-- Empty -->
    <div
      v-else-if="!loading"
      class="mt-3.5 rounded-xl bg-card p-10 text-center shadow-elevation-1"
    >
      <h3 class="font-serif text-[17px] font-bold leading-[25px]">
        {{ t("reps.emptyTitle") }}
      </h3>
      <p class="mx-auto mt-2 max-w-[44ch] text-sm leading-[21px] text-muted-foreground">
        {{ t("reps.emptyBody") }}
      </p>
      <Button
        variant="outline"
        class="mt-3.5"
        @click="clearFilters"
      >
        {{ t("common.clearFilters") }}
      </Button>
    </div>
    <p
      v-if="loading && !items.length"
      class="mt-6 text-center text-sm text-muted-foreground"
    >
      {{ t("common.loading") }}
    </p>

    <PaginationBar
      v-if="count > 50"
      class="pt-6"
      :current-page="page"
      :total="count"
      @page-change="reload"
    />

    <!-- Expired-hidden note -->
    <div
      class="mt-7 flex items-start gap-3 rounded-xl bg-warn p-[15px] text-warn-foreground shadow-elevation-1"
      role="note"
    >
      <LineIcon
        name="alert"
        class="mt-0.5 h-[19px] w-[19px] shrink-0"
      />
      <div>
        <h4 class="font-serif text-[14.5px] font-bold leading-[21px]">
          {{ t("reps.expiredTitle") }}
        </h4>
        <p class="mt-0.5 text-[13.5px] leading-5">
          {{ t("reps.expiredBody") }}
        </p>
      </div>
    </div>

    <!-- DOJ roster band -->
    <div class="mt-4 rounded-xl bg-band p-6 text-band-foreground">
      <div class="flex flex-wrap items-center justify-between gap-6">
        <div>
          <Eyebrow
            variant="onband"
            :parts="[t('reps.rosterEyebrow')]"
          />
          <h3 class="mt-2 max-w-[34ch] font-serif text-xl font-bold leading-7">
            {{ t("reps.rosterTitle") }}
          </h3>
          <p class="mt-2 max-w-[62ch] text-sm leading-6 text-band-quiet">
            {{ t("reps.rosterBody") }}
          </p>
        </div>
        <Button
          as-child
          variant="secondary"
          size="lg"
          class="bg-status text-status-foreground shadow-[var(--elevation-1-control),0_0_12px_2px_rgba(255,205,60,0.38)] max-md:w-full"
        >
          <a
            :href="EOIR_ROSTER_URL"
            target="_blank"
            rel="noopener noreferrer"
          >{{ t("reps.rosterButton") }}</a>
        </Button>
      </div>
    </div>

    <p class="mt-[22px] max-w-[80ch] text-xs leading-[18px] text-muted-foreground">
      {{ t("reps.disclaimer") }}
    </p>
  </div>
</template>
