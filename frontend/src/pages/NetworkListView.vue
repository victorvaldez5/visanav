<script setup lang="ts">
import {computed, ref} from "vue";
import {useRoute, useRouter} from "vue-router";
import {useI18n} from "vue-i18n";
import {networkService, type Organization, type OrganizationFilters} from "@/services/networkService.ts";
import {US_STATES} from "@/lib/usStates.ts";
import {useDirectoryFilters} from "@/composables/useDirectoryFilters.ts";
import {fmtDate, telHref} from "@/lib/format.ts";
import {selectClass, crossLinkClass} from "@/lib/directoryStyles.ts";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import PaginationBar from "@/components/interface/PaginationBar.vue";
import Eyebrow from "@/components/interface/Eyebrow.vue";
import LineIcon from "@/components/interface/LineIcon.vue";
import FilterChips from "@/components/interface/FilterChips.vue";
import FilterPanel from "@/components/interface/FilterPanel.vue";

// org_type values, from OrganizationType.choices in api/network/models.py; their
// labels are in the catalog under directory.types.
const TYPE_KEYS = [
  "self-owned",
  "public-company",
  "private-company",
  "partnership",
  "educational",
  "referral-service",
  "community-organization",
  "non-profit",
];
const FEE_KEYS = ["free", "sliding-scale", "low-cost", "paid"];
// Server ordering behind each sort option (DRF OrderingFilter).
const ORDERING: Record<string, string> = {
  name: "name",
  verified: "-last_verified",
  state: "address__subdivision__name,name",
};
const COST_IDS = ["pro_bono", "free", "low-cost", "sliding-scale"];
const {t, tm, rt} = useI18n();
const costItems = computed(() => COST_IDS.map((id) => ({id, label: t(`resources.costItems.${id}`)})));
const typeOptions = computed(() => TYPE_KEYS.map((value) => ({value, label: t(`directory.types.${value}`)})));
const eyebrow = computed(() => (tm("resources.eyebrow") as Parameters<typeof rt>[0][]).map((m) => rt(m)));
const route = useRoute();
const router = useRouter();

const search = ref(typeof route.query.q === "string" ? route.query.q : "");
const region = ref("");
const orgType = ref("");
const cost = ref<Record<string, boolean>>({});
const sort = ref("name");

function activeCost(): string[] {
  return Object.keys(cost.value).filter((k) => cost.value[k]);
}

function buildFilters(): OrganizationFilters {
  return {
    search: search.value || null,
    region: region.value || null,
    organizationType: orgType.value || null,
    cost: activeCost(),
    ordering: ORDERING[sort.value] ?? "name",
  };
}

// Filters shown in the mobile sheet (search stays visible, so it isn't counted).
const activeFilterCount = computed(
  () => (region.value ? 1 : 0) + (orgType.value ? 1 : 0) + activeCost().length,
);

const {items, page, count, loading, reload} = useDirectoryFilters<Organization, OrganizationFilters>({
  buildFilters,
  fetchPage: (p, f) => networkService.getOrganizations(p, f),
  errorMessage: () => t("resources.loadError"),
});

function costLabel(org: Organization): string | null {
  if (org.pro_bono) return t("directory.proBono");
  return FEE_KEYS.includes(org.fee_model) ? t(`directory.fees.${org.fee_model}`) : null;
}
function typeLabel(org: Organization): string {
  return TYPE_KEYS.includes(org.organization_type)
    ? t(`directory.types.${org.organization_type}`)
    : org.organization_type;
}
function websiteHref(url: string): string {
  return /^https?:/.test(url) ? url : "https://" + url;
}
function orgActions(org: Organization) {
  const acts: {icon: string; label: string; href: string; external?: boolean; tabular?: boolean}[] = [];
  if (org.phones.length) acts.push({icon: "phone", label: org.phones[0], href: telHref(org.phones[0]), tabular: true});
  if (org.emails.length) acts.push({icon: "mail", label: t("resources.email"), href: "mailto:" + org.emails[0]});
  if (org.websites.length) acts.push({icon: "globe", label: t("resources.website"), href: websiteHref(org.websites[0]), external: true});
  return acts;
}

function viewReps(org: Organization) {
  router.push({name: "Representatives", query: {q: org.name}});
}
function clearFilters() {
  search.value = "";
  region.value = "";
  orgType.value = "";
  cost.value = {};
  sort.value = "name";
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1180px] px-5 pb-10">
    <!-- Page head -->
    <header class="pb-[22px] pt-4">
      <Eyebrow :parts="eyebrow" />
      <h1 class="mt-2.5 font-serif text-[30px] font-bold leading-[38px] max-sm:text-2xl max-sm:leading-8">
        {{ t("resources.title") }}
      </h1>
      <p class="mt-2.5 max-w-[66ch] text-base leading-[25px] text-muted-foreground">
        {{ t("resources.intro") }}
      </p>
    </header>

    <!-- Notario caution — surfaced up top: the key "who can actually help you" note. -->
    <div
      class="mb-4 flex items-start gap-3 rounded-xl bg-warn p-[15px] text-warn-foreground shadow-elevation-1"
      role="note"
    >
      <LineIcon
        name="alert"
        class="mt-0.5 h-[19px] w-[19px] shrink-0"
      />
      <div>
        <h4 class="font-serif text-[14.5px] font-bold leading-[21px]">
          {{ t("resources.notarioTitle") }}
        </h4>
        <p class="mt-0.5 text-[13.5px] leading-5">
          {{ t("resources.notarioBody") }}
        </p>
      </div>
    </div>

    <!-- Filters -->
    <FilterPanel :active-count="activeFilterCount">
      <template #search>
        <div class="grid min-w-0 gap-1.5">
          <label
            for="o-search"
            class="text-sm font-medium leading-none"
          >{{ t("resources.searchLabel") }}</label>
          <Input
            id="o-search"
            v-model="search"
            type="search"
            autocomplete="off"
            :placeholder="t('resources.searchPlaceholder')"
            class="h-[38px] max-md:h-[46px]"
          />
        </div>
      </template>

      <div class="grid items-end gap-3 sm:grid-cols-2">
        <div class="grid min-w-0 gap-1.5">
          <label
            for="o-region"
            class="text-sm font-medium leading-none"
          >{{ t("common.state") }}</label>
          <select
            id="o-region"
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
        <div class="grid min-w-0 gap-1.5">
          <label
            for="o-type"
            class="text-sm font-medium leading-none"
          >{{ t("resources.orgType") }}</label>
          <select
            id="o-type"
            v-model="orgType"
            :class="selectClass"
          >
            <option value="">
              {{ t("resources.allTypes") }}
            </option>
            <option
              v-for="opt in typeOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>
      <div class="grid gap-[9px]">
        <span class="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">{{ t("common.cost") }}</span>
        <FilterChips
          v-model="cost"
          :items="costItems"
          :aria-label="t('common.cost')"
        />
      </div>
    </FilterPanel>

    <!-- Toolbar -->
    <div class="flex flex-wrap items-baseline justify-between gap-4 pb-4 pt-[26px] max-md:pt-4">
      <h2 class="font-serif text-[22px] font-bold leading-[30px] max-md:text-[20px] max-md:leading-[28px]">
        {{ region ? t("resources.countIn", {count, region}, count) : t("resources.count", count) }}
      </h2>
      <div class="flex items-center gap-2 text-sm text-muted-foreground max-md:grid max-md:w-full max-md:grid-cols-[auto_1fr]">
        <label for="o-sort">{{ t("common.sortBy") }}</label>
        <select
          id="o-sort"
          v-model="sort"
          :class="[selectClass, 'md:h-[34px] md:w-auto md:text-sm']"
        >
          <option value="name">
            {{ t("resources.sort.name") }}
          </option>
          <option value="verified">
            {{ t("resources.sort.verified") }}
          </option>
          <option value="state">
            {{ t("resources.sort.state") }}
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
        v-for="org in items"
        :key="org.id"
        class="flex flex-col rounded-xl bg-card p-[18px] text-card-foreground shadow-elevation-1 transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-elevation-2"
      >
        <div class="flex items-start justify-between gap-3 max-md:flex-col max-md:gap-2.5">
          <div class="min-w-0">
            <h3 class="font-serif text-[17px] font-bold leading-[25px] max-md:text-[18px] max-md:leading-[26px]">
              {{ org.name }}
            </h3>
            <p class="mt-0.5 text-[13px] leading-[18px] text-muted-foreground">
              {{ typeLabel(org) }}
            </p>
          </div>
          <div class="flex max-w-[52%] flex-none flex-wrap justify-end gap-1.5 max-md:max-w-full max-md:justify-start">
            <Badge
              v-if="costLabel(org)"
              variant="reassure"
            >
              {{ costLabel(org) }}
            </Badge>
            <Badge
              v-if="org.accreditation"
              variant="info"
            >
              {{ org.accreditation }}
            </Badge>
          </div>
        </div>

        <address
          v-if="org.address && (org.address.line1 || org.address.city)"
          class="mt-3 text-sm not-italic leading-[21px]"
        >
          <template v-if="org.address.line1">
            {{ org.address.line1 }}<br>
          </template>
          {{ org.address.city }}<template v-if="org.address.subdivision">
            , {{ org.address.subdivision.code }}
          </template>
          {{ org.address.postal_code }}
        </address>

        <p
          v-if="org.description"
          class="mt-2.5 line-clamp-3 text-[13.5px] leading-5 text-muted-foreground"
        >
          {{ org.description }}
        </p>

        <div class="mt-3">
          <Eyebrow
            variant="muted"
            :parts="[org.address?.subdivision?.code, org.last_verified ? t('resources.verified', {date: fmtDate(org.last_verified)}) : null]"
          />
        </div>

        <div class="mt-auto flex flex-wrap items-center gap-[9px] pt-3.5">
          <Button
            v-for="(a, i) in orgActions(org)"
            :key="a.icon"
            as-child
            :variant="i === 0 ? 'default' : 'outline'"
            size="sm"
            :class="['max-md:h-11', i === 0 ? 'max-md:w-full' : 'max-md:flex-1 max-md:basis-[140px]']"
          >
            <a
              :href="a.href"
              :target="a.external ? '_blank' : undefined"
              :rel="a.external ? 'noopener noreferrer' : undefined"
            >
              <LineIcon
                :name="a.icon"
                class="h-[15px] w-[15px]"
              />
              <span :class="{'tabular-nums': a.tabular}">{{ a.label }}</span>
            </a>
          </Button>
          <button
            type="button"
            :class="crossLinkClass"
            @click="viewReps(org)"
          >
            {{ t("resources.repsHere") }} <span aria-hidden="true">→</span>
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
        {{ t("resources.emptyTitle") }}
      </h3>
      <p class="mx-auto mt-2 max-w-[44ch] text-sm leading-[21px] text-muted-foreground">
        {{ t("resources.emptyBody") }}
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

    <!-- Chat CTA band -->
    <div class="mt-7 rounded-xl bg-band p-6 text-band-foreground">
      <div class="flex flex-wrap items-center justify-between gap-6">
        <div>
          <Eyebrow
            variant="onband"
            :parts="[t('resources.ctaEyebrow')]"
          />
          <h3 class="mt-2 max-w-[28ch] font-serif text-xl font-bold leading-7">
            {{ t("resources.ctaTitle") }}
          </h3>
          <p class="mt-2 max-w-[62ch] text-sm leading-6 text-band-quiet">
            {{ t("resources.ctaBody") }}
          </p>
        </div>
        <Button
          as-child
          variant="secondary"
          size="lg"
          class="bg-status text-status-foreground shadow-[var(--elevation-1-control),0_0_12px_2px_rgba(255,205,60,0.38)] max-md:w-full"
        >
          <RouterLink to="/">
            {{ t("resources.ctaButton") }}
          </RouterLink>
        </Button>
      </div>
    </div>

    <p class="mt-[22px] max-w-[80ch] text-xs leading-[18px] text-muted-foreground">
      {{ t("resources.disclaimer") }}
    </p>
  </div>
</template>
