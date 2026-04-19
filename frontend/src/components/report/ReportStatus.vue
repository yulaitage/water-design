<template>
  <div class="report-panel">
    <a-card title="报告生成" :bordered="false">
      <a-form layout="vertical" @finish="handleCreate">
        <a-form-item label="报告类型">
          <a-select v-model:value="reportType" style="width: 100%">
            <a-select-option value="feasibility">可行性研究报告</a-select-option>
            <a-select-option value="design">初步设计报告</a-select-option>
            <a-select-option value="construction">施工图设计说明</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="项目名称">
          <a-input v-model:value="projectInfo.name" placeholder="工程名称" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="项目地点">
              <a-input v-model:value="projectInfo.location" placeholder="所在地区" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="业主单位">
              <a-input v-model:value="projectInfo.owner" placeholder="建设单位" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="工程规模">
              <a-input v-model:value="projectInfo.scale" placeholder="如：堤防总长5km" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="项目描述">
              <a-input v-model:value="projectInfo.description" placeholder="简要描述" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="creating">生成报告</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <template v-if="currentTask">
      <a-card title="生成状态" :bordered="false" style="margin-top: 16px">
        <a-progress
          :percent="currentTask.progress"
          :status="progressStatus"
        />
        <a-descriptions :column="2" size="small" style="margin-top: 12px">
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor">{{ statusText }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="版本">v{{ currentTask.version }}</a-descriptions-item>
          <a-descriptions-item label="当前章节" :span="2">
            {{ currentTask.current_chapter || '-' }}
          </a-descriptions-item>
        </a-descriptions>

        <template v-if="currentTask.status === 'completed'">
          <a-button type="primary" @click="handleDownload">
            下载报告
          </a-button>
        </template>

        <a-alert
          v-if="currentTask.error"
          :message="currentTask.error"
          type="error"
          show-icon
          style="margin-top: 12px"
        />
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { reportsApi, type ReportStatus as ReportStatusType, type ProjectInfo } from '@/api/reports'

const props = defineProps<{ projectId: string }>()

const reportType = ref('feasibility')
const creating = ref(false)
const currentTask = ref<ReportStatusType | null>(null)
const pollingTimer = ref<ReturnType<typeof setInterval>>()

const projectInfo = reactive<ProjectInfo>({
  name: '',
  location: '',
  owner: '',
  scale: '',
  description: '',
})

const statusColor = computed(() => {
  const map: Record<string, string> = {
    pending: 'default',
    processing: 'processing',
    completed: 'success',
    failed: 'error',
    not_found: 'warning',
  }
  return map[currentTask.value?.status ?? ''] ?? 'default'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '生成中',
    completed: '已完成',
    failed: '失败',
    not_found: '未找到',
  }
  return map[currentTask.value?.status ?? ''] ?? currentTask.value?.status
})

const progressStatus = computed(() => {
  if (currentTask.value?.status === 'completed') return 'success' as const
  if (currentTask.value?.status === 'failed') return 'exception' as const
  return 'active' as const
})

async function handleCreate() {
  creating.value = true
  try {
    const task = (await reportsApi.create(props.projectId, reportType.value, projectInfo)).data
    currentTask.value = { task_id: task.task_id, status: task.status, progress: 0, current_chapter: null, version: task.version, error: null }
    startPolling()
    message.success('报告生成任务已创建')
  } catch {
    message.error('创建失败')
  } finally {
    creating.value = false
  }
}

function startPolling() {
  stopPolling()
  pollingTimer.value = setInterval(async () => {
    if (!currentTask.value) return
    try {
      const status = (await reportsApi.getStatus(props.projectId, currentTask.value.task_id)).data
      currentTask.value = status
      if (status.status === 'completed' || status.status === 'failed') {
        stopPolling()
      }
    } catch {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = undefined
  }
}

function handleDownload() {
  if (!currentTask.value) return
  const url = reportsApi.getDownloadUrl(props.projectId, currentTask.value.task_id)
  window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => stopPolling)
onUnmounted(() => stopPolling())
</script>

<style scoped>
.report-panel {
  max-width: 800px;
}
</style>
