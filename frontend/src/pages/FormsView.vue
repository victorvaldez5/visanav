<script setup lang="ts">
import { computed, ref } from "vue";
import forms from "@/data/forms.json";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface FormEntry {
  number: string;
  title: string;
  summary: string;
  category: string;
  url: string;
  fileOnline: boolean;
}

const all = forms as FormEntry[];
const categories = Array.from(new Set(all.map((f) => f.category))).sort();

const search = ref("");
const category = ref("");

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return all.filter((f) => {
    const matchesQuery =
      !q ||
      f.number.toLowerCase().includes(q) ||
      f.title.toLowerCase().includes(q) ||
      f.summary.toLowerCase().includes(q);
    const matchesCategory = !category.value || f.category === category.value;
    return matchesQuery && matchesCategory;
  });
});
</script>

<template>
  <div class="px-5 pb-10">
    <div class="mx-auto max-w-6xl">
      <header class="pt-2">
        <h2 class="text-2xl/7 font-semibold text-foreground sm:text-3xl sm:tracking-tight">
          Immigration forms
        </h2>
        <p class="mt-2 max-w-2xl text-sm text-muted-foreground">
          Browse common USCIS forms and what each one is for, in plain language.
          Free to look up — always download and file forms on the official USCIS
          website, which never charges for its forms or online accounts.
        </p>
      </header>

      <!-- Filters -->
      <div class="mt-6 flex flex-col gap-3 sm:flex-row">
        <Input
          v-model="search"
          type="search"
          autocomplete="off"
          placeholder="Search by number, name, or purpose — e.g. I-130, work permit"
          class="sm:flex-1"
        />
        <select
          v-model="category"
          aria-label="Filter by category"
          class="h-10 border border-border bg-card px-3 text-sm text-foreground shadow-sm outline-none focus:ring-2 focus:ring-ring sm:w-64"
        >
          <option value="">All categories</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>

      <p class="mt-4 text-sm text-muted-foreground" aria-live="polite">
        {{ filtered.length }} form{{ filtered.length === 1 ? "" : "s" }}
      </p>

      <!-- Results -->
      <ul class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <li
          v-for="form in filtered"
          :key="form.number"
          class="flex flex-col border border-border bg-card p-5 text-card-foreground shadow-sm"
        >
          <div class="flex items-center justify-between gap-2">
            <Badge variant="default" class="text-sm font-medium">{{ form.number }}</Badge>
            <Badge v-if="form.fileOnline" class="bg-primary font-medium text-primary-foreground">
              File online
            </Badge>
          </div>
          <h3 class="mt-3 font-semibold text-foreground">{{ form.title }}</h3>
          <p class="mt-1 flex-1 text-sm text-muted-foreground">{{ form.summary }}</p>
          <div class="mt-4 flex items-center justify-between gap-3">
            <span class="text-xs text-muted-foreground">{{ form.category }}</span>
            <a
              :href="form.url"
              target="_blank"
              rel="noopener noreferrer"
              class="shrink-0 text-sm font-semibold text-foreground underline underline-offset-4 hover:text-primary"
            >
              Official form →
            </a>
          </div>
        </li>
      </ul>

      <p
        v-if="filtered.length === 0"
        class="mt-10 text-center text-muted-foreground"
      >
        No forms match your search. Try a different term or category.
      </p>
    </div>
  </div>
</template>
