<template>
  <div class="terrain-panel">
    <a-card title="地形数据" :bordered="false">
      <a-upload-dragger
        :before-upload="handleUpload"
        :show-upload-list="false"
        accept=".csv,.dxf"
      >
        <p class="ant-upload-drag-icon">
          <inbox-outlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p class="ant-upload-hint">支持 CSV、DXF 格式</p>
      </a-upload-dragger>

      <a-progress
        v-if="uploadProgress > 0 && uploadProgress < 100"
        :percent="uploadProgress"
        style="margin-top: 16px"
      />

      <a-divider v-if="terrain" />

      <template v-if="terrain">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="文件类型">{{ terrain.file_type }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor">{{ statusText }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="断面数量">{{ terrain.feature_count ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="高程范围">
            <template v-if="elevationRange">
              {{ elevationRange[0].toFixed(2) }}m ~ {{ elevationRange[1].toFixed(2) }}m
            </template>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>

        <div v-if="terrain.status === 'completed'" style="margin-top: 16px">
          <a-button type="link" @click="refresh">
            <reload-outlined /> 重新解析
          </a-button>
        </div>
      </template>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { InboxOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { terrainApi, type TerrainData } from '@/api/terrain'

const props = defineProps<{ projectId: string }>()

const terrain = ref<TerrainData | null>(null)
const uploadProgress = ref(0)

const statusColor = computed(() => {
  const map: Record<string, string> = { pending: 'default', processing: 'processing', completed: 'success', failed: 'error' }
  return map[terrain.value?.status ?? ''] ?? 'default'
})

const statusText = computed(() => {
  const map: Record<string, string> = { pending: '待处理', processing: '解析中', completed: '已完成', failed: '失败' }
  return map[terrain.value?.status ?? ''] ?? terrain.value?.status
})

const elevationRange = computed(() => terrain.value?.features?.elevation_range)

async function handleUpload(file: File) {
  uploadProgress.value = 0
  try {
    await terrainApi.upload(props.projectId, file, (percent) => {
      uploadProgress.value = percent
    })
    message.success('文件上传成功')
    uploadProgress.value = 100
    await refresh()
  } catch {
    message.error('上传失败')
  } finally {
    uploadProgress.value = 0
  }
  return false
}

async function refresh() {
  try {
    terrain.value = (await terrainApi.get(props.projectId)).data
  } catch {
    terrain.value = null
  }
}

onMounted(refresh)
</script>

<style scoped>
.terrain-panel {
  max-width: 800px;
}
</style>
