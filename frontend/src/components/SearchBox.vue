<script setup>
const props = defineProps({
  searchQuery: String,
  searchResults: Array,
  activeFilters: Array
})

const emit = defineEmits(['update:searchQuery', 'handleSearch', 'selectSearchResult', 'removeFilter'])
</script>

<template>
  <div class="search-container">
    <div class="active-filters">
      <span v-for="tag in activeFilters" :key="tag" class="filter-tag">
        {{ tag }}
        <i @click="$emit('removeFilter', tag)">×</i>
      </span>
    </div>
    <input 
      :value="searchQuery" 
      @input="$emit('update:searchQuery', $event.target.value); $emit('handleSearch')"
      placeholder="搜索形象或标签..." 
    >
    <div v-if="searchResults.length > 0" class="search-results">
      <div 
        v-for="res in searchResults" 
        :key="res.id" 
        class="search-item"
        @click="$emit('selectSearchResult', res)"
      >
        <span class="res-type">{{ res.type === 'node' ? '形象' : '标签' }}</span>
        <span class="res-name">{{ res.name }}</span>
      </div>
    </div>
  </div>
</template>
