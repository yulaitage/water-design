<template>
  <a-layout class="workspace">
    <a-layout-sider width="200" theme="light">
      <div class="workspace-title">{{ projectName }}</div>
      <a-menu
        v-model:selectedKeys="activeMenu"
        mode="inline"
        :items="menuItems"
        @click="onMenuClick"
      />
    </a-layout-sider>
    <a-layout-content class="workspace-content">
      <TerrainUploader v-if="activePanel === 'terrain'" :project-id="projectId" />
      <ChatPanel v-else-if="activePanel === 'chat'" :project-id="projectId" />
      <CostEstimateForm v-else-if="activePanel === 'cost'" :project-id="projectId" />
      <ReportStatus v-else-if="activePanel === 'report'" :project-id="projectId" />
      <KnowledgeBase v-else-if="activePanel === 'knowledge'" :project-id="projectId" />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { projectsApi } from '@/api/projects'
import TerrainUploader from '@/components/terrain/TerrainUploader.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import CostEstimateForm from '@/components/cost/CostEstimateForm.vue'
import ReportStatus from '@/components/report/ReportStatus.vue'
import KnowledgeBase from '@/components/knowledge/KnowledgeBase.vue'

const route = useRoute()
const projectId = route.params.id as string
const projectName = ref('加载中...')

const menuItems = [
  { key: 'terrain', icon: 'EnvironmentOutlined', label: '地形数据' },
  { key: 'chat', icon: 'MessageOutlined', label: 'AI 对话' },
  { key: 'cost', icon: 'CalculatorOutlined', label: '费用估算' },
  { key: 'report', icon: 'FileTextOutlined', label: '报告生成' },
  { key: 'knowledge', icon: 'BookOutlined', label: '知识库' },
]

const activeMenu = ref<string[]>(['chat'])
const activePanel = ref('chat')

const onMenuClick = ({ key }: { key: string }) => {
  activeMenu.value = [key]
  activePanel.value = key
}

async function loadProject() {
  try {
    const project = (await projectsApi.get(projectId)).data
    projectName.value = project.name
  } catch {
    projectName.value = '项目不存在'
  }
}

onMounted(loadProject)
watch(() => route.params.id, (newId) => {
  if (newId) loadProject()
})
</script>

<style scoped>
.workspace {
  min-height: 100vh;
}

.workspace-title {
  padding: 16px 20px;
  font-size: 16px;
  font-weight: 600;
  color: #0891b2;
  border-bottom: 1px solid #f0f0f0;
}

.workspace-content {
  padding: 24px;
  background: linear-gradient(to bottom, #f0f9ff, #ffffff);
}
</style>
