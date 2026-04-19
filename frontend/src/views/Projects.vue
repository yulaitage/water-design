<template>
  <div class="projects-page">
    <a-page-header title="项目管理" subtitle="水利工程设计AI助理">
      <template #extra>
        <a-button type="primary" @click="openCreateModal">新建项目</a-button>
      </template>
    </a-page-header>

    <div class="projects-content">
      <a-table
        :columns="columns"
        :data-source="projectStore.projects"
        :loading="projectStore.loading"
        :pagination="{
          total: projectStore.total,
          pageSize: 20,
          showTotal: (t: number) => `共 ${t} 个项目`,
        }"
        row-key="id"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <router-link :to="`/projects/${record.id}`" class="project-name-link">
              {{ record.name }}
            </router-link>
          </template>

          <template v-if="column.key === 'description'">
            {{ record.description || '-' }}
          </template>

          <template v-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>

          <template v-if="column.key === 'action'">
            <a-space>
              <router-link :to="`/projects/${record.id}`">
                <a-button type="link" size="small">进入工作台</a-button>
              </router-link>
              <a-popconfirm
                title="确定删除此项目？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(record.id)"
              >
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>

        <template #emptyText>
          <a-empty description="暂无项目，点击右上角新建">
            <a-button type="primary" @click="openCreateModal">新建项目</a-button>
          </a-empty>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="createModalVisible"
      title="新建项目"
      ok-text="创建"
      cancel-text="取消"
      :confirm-loading="creating"
      @ok="handleCreate"
    >
      <a-form :model="createForm" layout="vertical">
        <a-form-item label="项目名称" required>
          <a-input
            v-model:value="createForm.name"
            placeholder="如：XX河道整治工程"
            :maxlength="200"
          />
        </a-form-item>
        <a-form-item label="项目描述">
          <a-textarea
            v-model:value="createForm.description"
            placeholder="简要描述项目背景和目标"
            :rows="3"
            :maxlength="1000"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'

const router = useRouter()
const projectStore = useProjectStore()

const createModalVisible = ref(false)
const creating = ref(false)
const createForm = reactive({ name: '', description: '' })

const columns = [
  { title: '项目名称', key: 'name', dataIndex: 'name' },
  { title: '描述', key: 'description', dataIndex: 'description', ellipsis: true },
  { title: '创建时间', key: 'created_at', dataIndex: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const },
]

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function openCreateModal() {
  createForm.name = ''
  createForm.description = ''
  createModalVisible.value = true
}

async function handleCreate() {
  if (!createForm.name.trim()) return
  creating.value = true
  try {
    const project = await projectStore.createProject({
      name: createForm.name.trim(),
      description: createForm.description.trim() || undefined,
    })
    createModalVisible.value = false
    router.push(`/projects/${project.id}`)
  } finally {
    creating.value = false
  }
}

async function handleDelete(id: string) {
  await projectStore.deleteProject(id)
}

function onTableChange() {
  projectStore.fetchProjects()
}

onMounted(() => {
  projectStore.fetchProjects()
})
</script>

<style scoped>
.projects-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.projects-content {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.project-name-link {
  color: #0891b2;
  font-weight: 500;
}

.project-name-link:hover {
  color: #0e7490;
}
</style>
