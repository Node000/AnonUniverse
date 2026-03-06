<script setup>
import { onMounted, onUnmounted, ref, reactive, nextTick, computed, watch } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

// State for Graph Logic
export function useGraph(apiBase, vizContainer, isDarkMode) {
  let network = null
  let nodesData = new DataSet([])
  let edgesData = new DataSet([])
  const loading = ref(true)
  const selectedNode = ref(null)
  const isPanelOpen = ref(false)
  const focusedNodeId = ref(null)
  const isConnectionEditMode = ref(false)

  // ... (Paste renderNodes, fetchGraphData, initializeNetwork here)

  return {
    network,
    nodesData,
    edgesData,
    loading,
    selectedNode,
    isPanelOpen,
    focusedNodeId,
    isConnectionEditMode,
    // Methods
    fetchGraphData
  }
}
