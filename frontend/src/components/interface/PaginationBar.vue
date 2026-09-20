<script setup lang="ts">
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'

defineEmits(['page-change'])

defineProps<{
  currentPage: number
  total?: number
  itemsPerPage?: number
}>()
</script>

<template>
  <Pagination
    v-slot="{ page }"
    :items-per-page="itemsPerPage || 50"
    :total="total"
    :default-page="currentPage"
    show-edges
  >
    <PaginationContent v-slot="{ items }">
      <PaginationPrevious @click="$emit('page-change', page - 1)" />

      <template
        v-for="(item, index) in items"
        :key="index"
      >
        <PaginationItem
          v-if="item.type === 'page'"
          :value="item.value"
          :is-active="item.value === page"
          @click="$emit('page-change', item.value)"
        >
          {{ item.value }}
        </PaginationItem>
      </template>
      <PaginationNext @click="$emit('page-change', page + 1)" />
    </PaginationContent>
  </Pagination>
</template>